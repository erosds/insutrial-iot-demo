# main.py - Sistema DAQ principale che orchestrare tutto il flusso dati
"""
Questo è il modulo principale del sistema DAQ che orchestrare tutto:
1. Connessione al server OPC UA
2. Lettura periodica dei dati sensori
3. Validazione e elaborazione dati
4. Invio a TimescaleDB
5. Monitoraggio e gestione errori

È il "cervello" che coordina tutti i componenti.
Versione sincrona per stabilità.
"""

import time
import signal
import sys
import os
from datetime import datetime, timezone
from typing import Dict, Any, List

# Aggiunge il path del progetto per gli import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importa moduli del sistema (ora con import assoluti)
from daq_system.config import settings
from daq_system.database import db_manager, sensor_db
from daq_system.opc_client import opc_client

# Logging avanzato
from loguru import logger

# =============================================================================
# CLASSE PRINCIPALE SISTEMA DAQ (VERSIONE SINCRONA)
# =============================================================================

class IndustrialDAQSystem:
    """
    Sistema DAQ principale che coordina acquisizione, elaborazione e storage dati.
    Versione sincrona per maggiore stabilità e semplicità.
    """
    
    def __init__(self):
        """
        Inizializza il sistema DAQ con tutte le configurazioni.
        """
        self.running = False
        self.paused = False
        
        # Statistiche operative
        self.stats = {
            'start_time': None,
            'total_cycles': 0,
            'successful_cycles': 0,
            'failed_cycles': 0,
            'total_data_points': 0,
            'anomalies_detected': 0,
            'last_cycle_time': None,
            'avg_cycle_duration': 0.0
        }
        
        # Buffer per elaborazioni avanzate
        self.data_history: List[Dict[str, Any]] = []
        self.anomaly_buffer: List[Dict[str, Any]] = []
        
        logger.info("🏭 IndustrialDAQSystem inizializzato")
    
    def initialize(self) -> bool:
        """
        Inizializza tutti i sottosistemi del DAQ (versione sincrona).
        """
        logger.info("🚀 Inizializzazione sistema DAQ...")
        
        try:
            # 1. Verifica configurazioni
            if not settings.validate():
                logger.error("❌ Configurazioni non valide")
                return False
            
            # 2. Test connessione database
            logger.info("📊 Test connessione TimescaleDB...")
            if not db_manager.test_connection():
                logger.error("❌ Connessione database fallita")
                return False
            logger.success("✅ Database connesso")
            
            # 3. Connessione server OPC UA
            logger.info("🔧 Connessione server OPC UA...")
            if not opc_client.connect():  # Ora è sincrono
                logger.error("❌ Connessione OPC UA fallita")
                return False
            logger.success("✅ OPC UA connesso")
            
            # 4. Discovery nodi sensori
            logger.info("🔍 Discovery sensori...")
            if not opc_client.discover_sensor_nodes():  # Ora è sincrono
                logger.error("❌ Discovery sensori fallita")
                return False
            logger.success("✅ Sensori mappati")
            
            # 5. Test lettura iniziale
            logger.info("📡 Test lettura sensori...")
            test_readings = opc_client.read_sensor_data()  # Ora è sincrono
            if not test_readings:
                logger.error("❌ Nessun dato sensore disponibile")
                return False
            logger.success(f"✅ {len(test_readings)} sensori attivi")
            
            # 6. Inizializza statistiche
            self.stats['start_time'] = datetime.now(timezone.utc)
            
            logger.success("🎯 Sistema DAQ inizializzato con successo!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Errore inizializzazione: {e}")
            return False
    
    def acquisition_cycle(self) -> bool:
        """
        Esegue un ciclo completo di acquisizione dati (versione sincrona).
        """
        cycle_start = time.time()
        self.stats['total_cycles'] += 1
        
        try:
            logger.debug(f"🔄 Avvio ciclo acquisizione #{self.stats['total_cycles']}")
            
            # 1. ACQUISIZIONE: Legge dati da tutti i sensori
            readings = opc_client.read_sensor_data()
            if not readings:
                logger.warning("⚠️ Nessun dato acquisito in questo ciclo")
                return False
            
            # 2. VALIDAZIONE: Controlla qualità e range dei dati
            validated_readings = self.validate_readings(readings)
            if not validated_readings:
                logger.warning("⚠️ Tutti i dati non hanno superato la validazione")
                return False
            
            # 3. ELABORAZIONE: Calcoli e analisi avanzate
            processed_readings = self.process_readings(validated_readings)
            
            # 4. RILEVAMENTO ANOMALIE: Controllo soglie e pattern
            anomalies = self.detect_anomalies(processed_readings)
            if anomalies:
                self.handle_anomalies(anomalies)
            
            # 5. STORAGE: Invio dati al database
            storage_success = opc_client.store_readings(processed_readings)
            
            # 6. AGGIORNAMENTO STATISTICHE
            self.update_statistics(processed_readings, storage_success)
            
            # 7. MAINTENANCE: Pulizia buffer e dati vecchi
            self.maintenance_tasks()
            
            # Calcola durata ciclo
            cycle_duration = time.time() - cycle_start
            self.stats['avg_cycle_duration'] = (
                (self.stats['avg_cycle_duration'] * (self.stats['total_cycles'] - 1) + cycle_duration) 
                / self.stats['total_cycles']
            )
            self.stats['last_cycle_time'] = datetime.now(timezone.utc)
            
            if storage_success:
                self.stats['successful_cycles'] += 1
                logger.info(f"✅ Ciclo #{self.stats['total_cycles']} completato "
                           f"({len(processed_readings)} punti dati, {cycle_duration:.2f}s)")
                return True
            else:
                logger.warning(f"⚠️ Ciclo #{self.stats['total_cycles']} parzialmente riuscito "
                              f"(storage fallito)")
                return False
                
        except Exception as e:
            self.stats['failed_cycles'] += 1
            logger.error(f"❌ Errore ciclo acquisizione #{self.stats['total_cycles']}: {e}")
            return False
    
    def validate_readings(self, readings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Valida le letture sensori contro soglie e criteri di qualità.
        
        Args:
            readings: Lista letture grezze
            
        Returns:
            List[Dict]: Lista letture validate
        """
        validated = []
        
        for reading in readings:
            try:
                sensor_type = reading['sensor_type']
                value = reading['value']
                quality = reading.get('quality', 100)
                
                # Controllo qualità minima
                if quality < settings.daq.min_quality_threshold:
                    logger.warning(f"❌ Qualità bassa {sensor_type}: {quality}% < {settings.daq.min_quality_threshold}%")
                    continue
                
                # Controllo range valori per tipo sensore
                if sensor_type == 'temperature':
                    if not (settings.daq.temperature_min <= value <= settings.daq.temperature_max):
                        logger.warning(f"❌ Temperatura fuori range: {value}°C "
                                     f"(range: {settings.daq.temperature_min}-{settings.daq.temperature_max})")
                        # Marca come anomalia ma mantieni il dato
                        reading['anomaly'] = 'OUT_OF_RANGE'
                
                elif sensor_type == 'pressure':
                    if not (settings.daq.pressure_min <= value <= settings.daq.pressure_max):
                        logger.warning(f"❌ Pressione fuori range: {value} bar "
                                     f"(range: {settings.daq.pressure_min}-{settings.daq.pressure_max})")
                        reading['anomaly'] = 'OUT_OF_RANGE'
                
                elif sensor_type == 'vibration':
                    if value > settings.daq.vibration_max:
                        logger.warning(f"❌ Vibrazione alta: {value} mm/s "
                                     f"(max: {settings.daq.vibration_max})")
                        reading['anomaly'] = 'HIGH_VIBRATION'
                
                # Se arriviamo qui, il dato è valido
                validated.append(reading)
                
            except Exception as e:
                logger.error(f"Errore validazione lettura: {e}")
                continue
        
        logger.debug(f"✅ Validate {len(validated)}/{len(readings)} letture")
        return validated
    
    def process_readings(self, readings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Elabora i dati validati con calcoli e filtri avanzati.
        
        Args:
            readings: Letture validate
            
        Returns:
            List[Dict]: Letture elaborate
        """
        processed = []
        
        for reading in readings:
            try:
                # Copia i dati originali
                processed_reading = reading.copy()
                
                # Aggiunge timestamp di elaborazione
                processed_reading['processed_at'] = datetime.now(timezone.utc)
                
                # Calcolo media mobile per ridurre rumore
                moving_avg = self.calculate_moving_average(
                    reading['sensor_type'], 
                    reading['value']
                )
                processed_reading['moving_average'] = moving_avg
                
                # Calcolo variazione rispetto alla media
                if moving_avg:
                    deviation = abs(reading['value'] - moving_avg)
                    processed_reading['deviation_from_avg'] = deviation
                    
                    # Marca deviazioni significative
                    if deviation > (moving_avg * 0.1):  # 10% di deviazione
                        processed_reading['high_deviation'] = True
                
                # Aggiunge metadati di elaborazione
                processed_reading['processing_version'] = '1.0'
                processed_reading['daq_system_id'] = 'DAQ_001'
                
                processed.append(processed_reading)
                
            except Exception as e:
                logger.error(f"Errore elaborazione lettura: {e}")
                # In caso di errore, mantiene il dato originale
                processed.append(reading)
        
        # Aggiorna storico per calcoli futuri
        self.data_history.extend(processed)
        # Mantiene solo gli ultimi 1000 punti per performance
        if len(self.data_history) > 1000:
            self.data_history = self.data_history[-1000:]
        
        logger.debug(f"🔧 Elaborate {len(processed)} letture")
        return processed
    
    def calculate_moving_average(self, sensor_type: str, current_value: float, window: int = 5) -> float:
        """
        Calcola la media mobile per un sensore specifico.
        
        Args:
            sensor_type: Tipo sensore
            current_value: Valore corrente
            window: Finestra per media mobile
            
        Returns:
            float: Media mobile calcolata
        """
        # Filtra storico per il sensore specifico
        sensor_history = [
            point['value'] for point in self.data_history 
            if point.get('sensor_type') == sensor_type
        ]
        
        # Aggiunge valore corrente
        sensor_history.append(current_value)
        
        # Calcola media degli ultimi N valori
        recent_values = sensor_history[-window:]
        if recent_values:
            return sum(recent_values) / len(recent_values)
        
        return current_value
    
    def detect_anomalies(self, readings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rileva anomalie nei dati usando algoritmi avanzati e soglie configurabili.
        
        Args:
            readings: Lista letture elaborate
            
        Returns:
            List[Dict]: Lista anomalie rilevate
        """
        anomalies = []
        
        for reading in readings:
            try:
                # Anomalie già marcate nella validazione
                if reading.get('anomaly'):
                    anomaly = {
                        'timestamp': reading['timestamp'],
                        'machine_id': reading['machine_id'],
                        'sensor_type': reading['sensor_type'],
                        'value': reading['value'],
                        'anomaly_type': reading['anomaly'],
                        'severity': self._calculate_severity(reading),
                        'description': self._get_anomaly_description(reading['anomaly'], reading)
                    }
                    anomalies.append(anomaly)
                
                # Rilevamento deviazioni significative dalla media mobile
                if reading.get('high_deviation'):
                    anomaly = {
                        'timestamp': reading['timestamp'],
                        'machine_id': reading['machine_id'],
                        'sensor_type': reading['sensor_type'],
                        'value': reading['value'],
                        'anomaly_type': 'HIGH_DEVIATION',
                        'severity': 'MEDIUM',
                        'description': f"Deviazione significativa dalla media mobile: {reading.get('deviation_from_avg', 0):.2f}"
                    }
                    anomalies.append(anomaly)
                
                # Rilevamento pattern anomali (cambi rapidi)
                rapid_change = self._detect_rapid_change(reading)
                if rapid_change:
                    anomaly = {
                        'timestamp': reading['timestamp'],
                        'machine_id': reading['machine_id'],
                        'sensor_type': reading['sensor_type'],
                        'value': reading['value'],
                        'anomaly_type': 'RAPID_CHANGE',
                        'severity': 'HIGH',
                        'description': f"Cambiamento rapido rilevato: {rapid_change}"
                    }
                    anomalies.append(anomaly)
                    
            except Exception as e:
                logger.error(f"Errore rilevamento anomalie: {e}")
                continue
        
        if anomalies:
            logger.warning(f"🚨 Rilevate {len(anomalies)} anomalie")
            self.stats['anomalies_detected'] += len(anomalies)
        
        return anomalies
    
    def _calculate_severity(self, reading: Dict[str, Any]) -> str:
        """
        Calcola la gravità di un'anomalia basandosi sul tipo e valore.
        """
        anomaly_type = reading.get('anomaly', '')
        sensor_type = reading['sensor_type']
        value = reading['value']
        
        if anomaly_type == 'OUT_OF_RANGE':
            if sensor_type == 'temperature':
                if value > 35 or value < 20:
                    return 'HIGH'
                return 'MEDIUM'
            elif sensor_type == 'pressure':
                if value > 1.8 or value < 1.0:
                    return 'HIGH'
                return 'MEDIUM'
        elif anomaly_type == 'HIGH_VIBRATION':
            if value > 2.0:
                return 'CRITICAL'
            return 'HIGH'
        
        return 'LOW'
    
    def _get_anomaly_description(self, anomaly_type: str, reading: Dict[str, Any]) -> str:
        """
        Genera descrizione dettagliata dell'anomalia.
        """
        descriptions = {
            'OUT_OF_RANGE': f"Valore {reading['value']:.2f} {reading['unit']} fuori dai limiti operativi",
            'HIGH_VIBRATION': f"Vibrazione elevata {reading['value']:.2f} mm/s - possibile malfunzionamento",
            'LOW_QUALITY': f"Qualità segnale bassa: {reading.get('quality', 0)}%"
        }
        return descriptions.get(anomaly_type, f"Anomalia {anomaly_type} rilevata")
    
    def _detect_rapid_change(self, reading: Dict[str, Any]) -> str:
        """
        Rileva cambiamenti rapidi nei valori dei sensori.
        """
        sensor_type = reading['sensor_type']
        current_value = reading['value']
        
        # Cerca valori precedenti dello stesso sensore
        previous_values = [
            point['value'] for point in self.data_history[-10:]  # Ultimi 10 punti
            if point.get('sensor_type') == sensor_type
        ]
        
        if len(previous_values) >= 2:
            last_value = previous_values[-1]
            change_rate = abs(current_value - last_value)
            
            # Soglie per cambiamenti rapidi per tipo sensore
            thresholds = {
                'temperature': 5.0,  # 5°C di cambiamento
                'pressure': 0.3,     # 0.3 bar di cambiamento
                'vibration': 0.5     # 0.5 mm/s di cambiamento
            }
            
            threshold = thresholds.get(sensor_type, 1.0)
            if change_rate > threshold:
                return f"Cambiamento di {change_rate:.2f} {reading['unit']} in un ciclo"
        
        return None
    
    def handle_anomalies(self, anomalies: List[Dict[str, Any]]):
        """
        Gestisce le anomalie rilevate con azioni appropriate.
        
        Args:
            anomalies: Lista anomalie da gestire
        """
        for anomaly in anomalies:
            try:
                # Log dettagliato dell'anomalia
                severity = anomaly['severity']
                if severity == 'CRITICAL':
                    logger.critical(f"🔴 CRITICO: {anomaly['description']}")
                elif severity == 'HIGH':
                    logger.error(f"🟠 ALTO: {anomaly['description']}")
                elif severity == 'MEDIUM':
                    logger.warning(f"🟡 MEDIO: {anomaly['description']}")
                else:
                    logger.info(f"🔵 BASSO: {anomaly['description']}")
                
                # Salva anomalia nel buffer per analisi successive
                self.anomaly_buffer.append(anomaly)
                
                # Azioni automatiche basate sulla gravità
                if severity in ['CRITICAL', 'HIGH']:
                    # In un sistema reale, qui si potrebbero:
                    # - Inviare alert via email/SMS
                    # - Attivare allarmi visivi/sonori
                    # - Fermare automaticamente macchinari pericolosi
                    logger.info(f"🚨 Attivazione protocolli emergenza per {anomaly['sensor_type']}")
                
                # Salva anomalia nel database per storico
                self._store_anomaly(anomaly)
                
            except Exception as e:
                logger.error(f"Errore gestione anomalia: {e}")
    
    def _store_anomaly(self, anomaly: Dict[str, Any]):
        """
        Salva l'anomalia nel database per analisi storiche.
        """
        try:
            # Crea record anomalia per database
            anomaly_record = {
                'timestamp': anomaly['timestamp'],
                'machine_id': anomaly['machine_id'],
                'sensor_type': 'anomaly',  # Tipo speciale per anomalie
                'location': settings.daq.location,
                'value': 1.0,  # Valore dummy per indicare presenza anomalia
                'unit': 'count',
                'quality': 100,
                'status': anomaly['anomaly_type']
            }
            
            # Usa il sistema standard per salvare
            sensor_db.insert_sensor_reading(**anomaly_record)
            
        except Exception as e:
            logger.error(f"Errore salvataggio anomalia: {e}")
    
    def update_statistics(self, readings: List[Dict[str, Any]], storage_success: bool):
        """
        Aggiorna le statistiche operative del sistema.
        """
        self.stats['total_data_points'] += len(readings)
        
        # Calcola tempo di funzionamento
        if self.stats.get('start_time'):
            uptime = datetime.now(timezone.utc) - self.stats['start_time']
            self.stats['uptime_seconds'] = uptime.total_seconds()
            self.stats['uptime_hours'] = uptime.total_seconds() / 3600
    
    def maintenance_tasks(self):
        """
        Esegue task di manutenzione periodica del sistema.
        """
        # Pulizia buffer anomalie (mantiene solo ultime 100)
        if len(self.anomaly_buffer) > 100:
            self.anomaly_buffer = self.anomaly_buffer[-100:]
        
        # Log statistiche ogni 100 cicli
        if self.stats['total_cycles'] % 100 == 0:
            self.log_statistics()
    
    def log_statistics(self):
        """
        Stampa statistiche dettagliate del sistema.
        """
        stats = self.get_detailed_statistics()
        
        logger.info("📊 === STATISTICHE SISTEMA DAQ ===")
        logger.info(f"⏱️  Uptime: {stats.get('uptime_hours', 0):.1f} ore")
        logger.info(f"🔄 Cicli: {stats['total_cycles']} (✅ {stats['successful_cycles']}, ❌ {stats['failed_cycles']})")
        logger.info(f"📈 Success rate: {stats['success_rate']:.1f}%")
        logger.info(f"📊 Punti dati: {stats['total_data_points']}")
        logger.info(f"🚨 Anomalie: {stats['anomalies_detected']}")
        logger.info(f"⚡ Durata media ciclo: {stats['avg_cycle_duration']:.2f}s")
        logger.info("==================================")
    
    def get_detailed_statistics(self) -> Dict[str, Any]:
        """
        Restituisce statistiche dettagliate del sistema.
        """
        # Calcola success rate
        success_rate = 0
        if self.stats['total_cycles'] > 0:
            success_rate = (self.stats['successful_cycles'] / self.stats['total_cycles']) * 100
        
        # Calcola uptime
        uptime_hours = 0
        if self.stats.get('start_time'):
            uptime = datetime.now(timezone.utc) - self.stats['start_time']
            uptime_hours = uptime.total_seconds() / 3600
        
        # Combina statistiche DAQ e OPC client
        opc_stats = opc_client.get_statistics()
        db_stats = sensor_db.get_database_stats()
        
        return {
            **self.stats,
            'success_rate': success_rate,
            'uptime_hours': uptime_hours,
            'opc_client': opc_stats,
            'database': db_stats
        }
    
    def run(self):
        """
        Loop principale del sistema DAQ (versione sincrona).
        """
        logger.info("🏃 Avvio loop principale sistema DAQ")
        
        self.running = True
        consecutive_failures = 0
        max_consecutive_failures = 5
        
        while self.running:
            try:
                if not self.paused:
                    # Esegue ciclo di acquisizione
                    cycle_success = self.acquisition_cycle()
                    
                    if cycle_success:
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                        
                        # Se troppi fallimenti consecutivi, pausa temporanea
                        if consecutive_failures >= max_consecutive_failures:
                            logger.error(f"❌ {consecutive_failures} fallimenti consecutivi - pausa 30s")
                            time.sleep(30)
                            consecutive_failures = 0
                    
                    # Attende prima del prossimo ciclo
                    time.sleep(settings.daq.acquisition_interval)
                else:
                    # Sistema in pausa
                    time.sleep(1)
                    
            except KeyboardInterrupt:
                logger.info("⌨️ Interruzione da tastiera ricevuta")
                break
            except Exception as e:
                logger.error(f"❌ Errore critico nel loop principale: {e}")
                consecutive_failures += 1
                time.sleep(5)  # Pausa prima di riprovare
        
        logger.info("🛑 Loop principale sistema DAQ terminato")
    
    def shutdown(self):
        """
        Arresta il sistema DAQ in modo pulito (versione sincrona).
        """
        logger.info("🛑 Avvio procedura di arresto sistema DAQ...")
        
        # Ferma loop principale
        self.running = False
        
        # Disconnette client OPC UA
        opc_client.disconnect()  # Ora è sincrono
        
        # Log statistiche finali
        self.log_statistics()
        
        # Salva eventuali dati rimanenti nel buffer
        if opc_client.data_buffer:
            logger.info("💾 Salvataggio dati finali dal buffer...")
            sensor_db.insert_batch_readings(opc_client.data_buffer)
        
        logger.success("✅ Sistema DAQ arrestato correttamente")
    
    def pause(self):
        """Mette in pausa il sistema DAQ."""
        self.paused = True
        logger.info("⏸️ Sistema DAQ in pausa")
    
    def resume(self):
        """Riprende il sistema DAQ dalla pausa."""
        self.paused = False
        logger.info("▶️ Sistema DAQ ripreso")

# =============================================================================
# ISTANZA GLOBALE E GESTIONE SEGNALI
# =============================================================================

# Istanza globale del sistema DAQ
daq_system = None

def signal_handler(signum, frame):
    """
    Gestisce segnali di sistema per arresto pulito.
    """
    logger.info(f"🛑 Ricevuto segnale {signum} - arresto sistema...")
    
    if daq_system:
        # Crea task asincrono per shutdown
        asyncio.create_task(daq_system.shutdown())
    
    sys.exit(0)

def signal_handler(signum, frame):
    """
    Gestisce segnali di sistema per arresto pulito.
    """
    logger.info(f"🛑 Ricevuto segnale {signum} - arresto sistema...")
    
    if daq_system:
        # Arresto sincrono
        daq_system.shutdown()
    
    sys.exit(0)

def main():
    """
    Funzione principale per avvio del sistema DAQ (versione sincrona).
    """
    global daq_system
    
    # Configura gestione segnali
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Crea e inizializza sistema DAQ
        daq_system = IndustrialDAQSystem()
        
        if daq_system.initialize():
            logger.success("🎯 Sistema DAQ pronto - avvio acquisizione dati...")
            
            # Avvia loop principale
            daq_system.run()
        else:
            logger.error("❌ Inizializzazione fallita - arresto sistema")
            return
            
    except KeyboardInterrupt:
        logger.info("⌨️ Interruzione utente")
    except Exception as e:
        logger.error(f"❌ Errore fatale: {e}")
    finally:
        # Cleanup finale
        if daq_system:
            daq_system.shutdown()

# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    """
    Entry point principale del sistema DAQ.
    """
    print("🏭 Industrial IoT DAQ System")
    print("============================")
    print(f"Machine ID: {settings.daq.machine_id}")
    print(f"Location: {settings.daq.location}")
    print(f"Acquisition Interval: {settings.daq.acquisition_interval}s")
    print(f"Batch Size: {settings.daq.batch_size}")
    print(f"OPC UA Endpoint: {settings.opc_server.endpoint}")
    print(f"Database: {settings.database.get_connection_string()}")
    print("\nPremi Ctrl+C per fermare il sistema\n")
    
    # Crea directory logs se non esiste
    os.makedirs("logs", exist_ok=True)
    
    # Configura logging
    logger.remove()  # Rimuove handler default
    
    # Log su file
    logger.add(
        settings.logging.log_file,
        rotation=settings.logging.max_file_size,
        retention=settings.logging.backup_count,
        level=settings.logging.level,
        format=settings.logging.format_string,
        compression="zip"  # Comprime i file vecchi
    )
    
    # Log su console con formato semplificato
    logger.add(
        sys.stdout,
        level=settings.logging.level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        colorize=True
    )
    
    # Avvia sistema sincrono
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Sistema fermato dall'utente")
    except Exception as e:
        print(f"\n❌ Errore fatale: {e}")
        sys.exit(1)