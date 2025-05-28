# opc_client.py - Client OPC UA per acquisizione dati DAQ (VERSIONE SINCRONA)
"""
Questo modulo implementa il client OPC UA che si connette al server
e legge i valori dei sensori per il sistema DAQ.
È responsabile della comunicazione tra il server OPC UA e il database.
VERSIONE COMPLETAMENTE SINCRONA per compatibilità con il sistema DAQ.
"""

import time
import sys
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

# Libreria OPC UA (versione sincrona)
from opcua import Client, ua
from opcua.common.node import Node
from loguru import logger

# Aggiunge il path del progetto per gli import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importa configurazioni e database (import assoluti)
from daq_system.config import settings
from daq_system.database import sensor_db

# =============================================================================
# CLASSE CLIENT OPC UA INDUSTRIALE (VERSIONE SINCRONA)
# =============================================================================

class IndustrialOPCClient:
    """
    Client OPC UA che si connette al server e acquisisce dati sensori.
    Versione completamente sincrona per compatibilità con il sistema DAQ principale.
    """
    
    def __init__(self):
        """
        Inizializza il client OPC UA con configurazioni da config.py
        """
        self.client = None
        self.connected = False
        self.sensor_nodes: Dict[str, Dict[str, Node]] = {}
        
        # Buffer per dati non inviati (in caso di problemi database)
        self.data_buffer: List[Dict[str, Any]] = []
        
        # Statistiche operative
        self.stats = {
            'total_readings': 0,
            'successful_readings': 0,
            'failed_readings': 0,
            'last_reading_time': None,
            'connection_attempts': 0
        }
        
        logger.info("IndustrialOPCClient inizializzato")
    
    def connect(self) -> bool:
        """
        Stabilisce connessione con il server OPC UA (VERSIONE SINCRONA).
        Implementa retry automatico in caso di fallimenti.
        
        Returns:
            bool: True se connessione riuscita
        """
        max_retries = 5
        retry_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                self.stats['connection_attempts'] += 1
                
                # Crea istanza client OPC UA
                self.client = Client(settings.opc_server.endpoint)
                
                # Connessione al server (SINCRONO)
                self.client.connect()
                
                # Verifica connessione con metodo più robusto
                try:
                    # Tenta di leggere informazioni del server
                    server_info = self.client.get_server_node()
                    logger.info(f"Connesso al server OPC UA: {server_info}")
                except:
                    # Se fallisce, usa verifica più semplice
                    root_node = self.client.get_root_node()
                    logger.info(f"Connesso al server OPC UA - verifica base OK")
                
                self.connected = True
                logger.success(f"✅ Connessione OPC UA stabilita (tentativo {attempt + 1})")
                
                return True
                
            except Exception as e:
                logger.warning(f"Tentativo connessione {attempt + 1} fallito: {e}")
                
                if attempt < max_retries - 1:
                    logger.info(f"Retry in {retry_delay} secondi...")
                    time.sleep(retry_delay)  # SINCRONO invece di await
                    retry_delay *= 1.5  # Backoff esponenziale
                else:
                    logger.error("❌ Impossibile connettersi al server OPC UA dopo tutti i tentativi")
                    return False
    
    def discover_sensor_nodes(self) -> bool:
        """
        Scopre automaticamente i nodi sensori nel server OPC UA (VERSIONE SINCRONA).
        Naviga la struttura ad albero per trovare i nodi di interesse.
        
        Returns:
            bool: True se nodi trovati con successo
        """
        if not self.connected:
            logger.error("Client non connesso - impossibile scoprire nodi")
            return False
        
        try:
            logger.info("🔍 Inizio discovery dei nodi sensori...")
            
            # Ottiene il nodo root degli oggetti (SINCRONO)
            objects_node = self.client.get_objects_node()
            
            # Cerca la cartella della macchina (SINCRONO)
            machine_folder = None
            for child in objects_node.get_children():  # SINCRONO
                try:
                    # Usa get_display_name() invece di read_display_name()
                    display_name = child.get_display_name()  # SINCRONO
                    if f"Machine_{settings.daq.machine_id}" in display_name.Text:
                        machine_folder = child
                        break
                except:
                    # Se fallisce, prova con get_browse_name()
                    try:
                        browse_name = child.get_browse_name()
                        if f"Machine_{settings.daq.machine_id}" in browse_name.Name:
                            machine_folder = child
                            break
                    except:
                        continue
            
            if not machine_folder:
                logger.error(f"Cartella macchina non trovata per ID: {settings.daq.machine_id}")
                return False
            
            logger.info(f"Trovata cartella macchina")
            
            # Cerca cartella sensori (SINCRONO)
            sensors_folder = None
            for child in machine_folder.get_children():  # SINCRONO
                try:
                    display_name = child.get_display_name()  # SINCRONO
                    if "Sensors" in display_name.Text:
                        sensors_folder = child
                        break
                except:
                    try:
                        browse_name = child.get_browse_name()
                        if "Sensors" in browse_name.Name:
                            sensors_folder = child
                            break
                    except:
                        continue
            
            if not sensors_folder:
                logger.error("Cartella Sensors non trovata")
                return False
            
            # Scopre tutti i sensori nella cartella (SINCRONO)
            sensor_folders = sensors_folder.get_children()  # SINCRONO
            
            for sensor_folder in sensor_folders:
                try:
                    sensor_name = sensor_folder.get_display_name()  # SINCRONO
                    sensor_name_text = sensor_name.Text if hasattr(sensor_name, 'Text') else str(sensor_name)
                except:
                    try:
                        sensor_name = sensor_folder.get_browse_name()
                        sensor_name_text = sensor_name.Name if hasattr(sensor_name, 'Name') else str(sensor_name)
                    except:
                        logger.warning("Impossibile ottenere nome sensore - skip")
                        continue
                
                logger.info(f"Analizzando sensore: {sensor_name_text}")
                
                # Trova i nodi specifici di ogni sensore (SINCRONO)
                sensor_nodes = {}
                for node in sensor_folder.get_children():  # SINCRONO
                    try:
                        node_name = node.get_display_name()  # SINCRONO
                        node_key = node_name.Text.lower() if hasattr(node_name, 'Text') else str(node_name).lower()
                        sensor_nodes[node_key] = node
                    except:
                        try:
                            node_name = node.get_browse_name()
                            node_key = node_name.Name.lower() if hasattr(node_name, 'Name') else str(node_name).lower()
                            sensor_nodes[node_key] = node
                        except:
                            continue
                
                # Verifica che abbiamo i nodi essenziali
                if 'value' in sensor_nodes:
                    # Determina il tipo di sensore dal nome
                    sensor_type = self._determine_sensor_type(sensor_name_text)
                    
                    if sensor_type:
                        self.sensor_nodes[sensor_type] = {
                            'value': sensor_nodes.get('value'),
                            'quality': sensor_nodes.get('quality'),
                            'timestamp': sensor_nodes.get('timestamp'),
                            'status': sensor_nodes.get('status'),
                            'display_name': sensor_name_text
                        }
                        
                        logger.success(f"✅ Sensore {sensor_type} mappato correttamente")
                    else:
                        logger.warning(f"Tipo sensore non riconosciuto: {sensor_name_text}")
                else:
                    logger.warning(f"Nodo 'Value' non trovato per {sensor_name_text}")
            
            logger.success(f"🎯 Discovery completata: {len(self.sensor_nodes)} sensori mappati")
            return len(self.sensor_nodes) > 0
            
        except Exception as e:
            logger.error(f"Errore durante discovery nodi: {e}")
            return False
    
    def _determine_sensor_type(self, display_name: str) -> Optional[str]:
        """
        Determina il tipo di sensore dal nome visualizzato.
        
        Args:
            display_name: Nome del sensore nel server OPC UA
            
        Returns:
            str: Tipo sensore standardizzato (temperature, pressure, vibration)
        """
        display_name_lower = display_name.lower()
        
        if 'temperature' in display_name_lower or 'temp' in display_name_lower:
            return 'temperature'
        elif 'pressure' in display_name_lower or 'press' in display_name_lower:
            return 'pressure'
        elif 'vibration' in display_name_lower or 'vib' in display_name_lower:
            return 'vibration'
        else:
            return None
    
    def read_sensor_data(self) -> List[Dict[str, Any]]:
        """
        Legge i valori attuali di tutti i sensori configurati (VERSIONE SINCRONA).
        Gestisce errori di lettura individuali senza bloccare gli altri sensori.
        
        Returns:
            List[Dict]: Lista di letture sensori con metadati
        """
        if not self.connected:
            logger.error("Client non connesso - impossibile leggere dati")
            return []
        
        readings = []
        current_time = datetime.now(timezone.utc)
        
        for sensor_type, nodes in self.sensor_nodes.items():
            try:
                # Legge valore principale del sensore (SINCRONO)
                # Prova diversi metodi per leggere il valore
                try:
                    value_variant = nodes['value'].get_value()  # Metodo più comune
                except:
                    try:
                        value_variant = nodes['value'].read_value()  # Metodo alternativo
                    except:
                        # Ultimo tentativo con get_data_value
                        data_value = nodes['value'].get_data_value()
                        value_variant = data_value.Value.Value if hasattr(data_value, 'Value') else data_value
                
                value = float(value_variant)
                
                # Legge qualità se disponibile (SINCRONO)
                quality = 100  # Default
                if nodes.get('quality'):
                    try:
                        quality_variant = nodes['quality'].get_value()  # SINCRONO
                        quality = int(quality_variant)
                    except:
                        try:
                            quality_variant = nodes['quality'].read_value()
                            quality = int(quality_variant)
                        except:
                            pass  # Usa valore default
                
                # Legge stato se disponibile (SINCRONO)
                status = 'OK'  # Default
                if nodes.get('status'):
                    try:
                        status_variant = nodes['status'].get_value()  # SINCRONO
                        status = str(status_variant)
                    except:
                        try:
                            status_variant = nodes['status'].read_value()
                            status = str(status_variant)
                        except:
                            pass  # Usa valore default
                
                # Legge timestamp del sensore se disponibile (SINCRONO)
                sensor_timestamp = current_time
                if nodes.get('timestamp'):
                    try:
                        timestamp_variant = nodes['timestamp'].get_value()  # SINCRONO
                        if timestamp_variant:
                            sensor_timestamp = timestamp_variant.replace(tzinfo=timezone.utc)
                    except:
                        try:
                            timestamp_variant = nodes['timestamp'].read_value()
                            if timestamp_variant:
                                sensor_timestamp = timestamp_variant.replace(tzinfo=timezone.utc)
                        except:
                            pass  # Usa timestamp corrente
                
                # Determina unità di misura basata sul tipo sensore
                unit = self._get_sensor_unit(sensor_type)
                
                # Crea record lettura
                reading = {
                    'timestamp': sensor_timestamp,
                    'machine_id': settings.daq.machine_id,
                    'sensor_type': sensor_type,
                    'location': settings.daq.location,
                    'value': value,
                    'unit': unit,
                    'quality': quality,
                    'status': status
                }
                
                readings.append(reading)
                
                logger.debug(f"Letto {sensor_type}: {value:.2f} {unit} (Q:{quality}%, S:{status})")
                
                self.stats['successful_readings'] += 1
                
            except Exception as e:
                logger.error(f"Errore lettura sensore {sensor_type}: {e}")
                self.stats['failed_readings'] += 1
                continue
        
        self.stats['total_readings'] += len(readings)
        self.stats['last_reading_time'] = current_time
        
        logger.info(f"📊 Completata lettura batch: {len(readings)} sensori")
        return readings
    
    def _get_sensor_unit(self, sensor_type: str) -> str:
        """
        Restituisce l'unità di misura per un tipo di sensore.
        
        Args:
            sensor_type: Tipo sensore
            
        Returns:
            str: Unità di misura
        """
        units = {
            'temperature': '°C',
            'pressure': 'bar',
            'vibration': 'mm/s'
        }
        return units.get(sensor_type, 'unknown')
    
    def store_readings(self, readings: List[Dict[str, Any]]) -> bool:
        """
        Invia le letture al database TimescaleDB (VERSIONE SINCRONA).
        Gestisce buffer locale in caso di problemi di connessione database.
        
        Args:
            readings: Lista di letture da memorizzare
            
        Returns:
            bool: True se memorizzazione riuscita
        """
        if not readings:
            return True
        
        try:
            # Aggiunge le nuove letture al buffer
            self.data_buffer.extend(readings)
            
            # Se il buffer è abbastanza grande, invia tutto in batch
            if len(self.data_buffer) >= settings.daq.batch_size:
                inserted_count = sensor_db.insert_batch_readings(self.data_buffer)
                
                if inserted_count > 0:
                    logger.success(f"💾 Salvati {inserted_count} record nel database")
                    
                    # Svuota buffer dopo invio riuscito
                    self.data_buffer.clear()
                    return True
                else:
                    logger.warning("Errore salvataggio - dati mantenuti in buffer")
                    
                    # Limita dimensione buffer per evitare memory leak
                    if len(self.data_buffer) > settings.daq.max_buffer_size:
                        # Rimuove i dati più vecchi
                        overflow = len(self.data_buffer) - settings.daq.max_buffer_size
                        self.data_buffer = self.data_buffer[overflow:]
                        logger.warning(f"Buffer overflow: rimossi {overflow} record più vecchi")
                    
                    return False
            else:
                logger.debug(f"Buffer: {len(self.data_buffer)}/{settings.daq.batch_size} record")
                return True
                
        except Exception as e:
            logger.error(f"Errore memorizzazione letture: {e}")
            return False
    
    def disconnect(self):
        """
        Disconnette il client dal server OPC UA in modo pulito (VERSIONE SINCRONA).
        """
        try:
            if self.connected and self.client:
                # Invia eventuali dati rimanenti nel buffer
                if self.data_buffer:
                    logger.info(f"Invio ultimi {len(self.data_buffer)} record dal buffer...")
                    sensor_db.insert_batch_readings(self.data_buffer)
                    self.data_buffer.clear()
                
                # Disconnessione sincrona
                self.client.disconnect()  # SINCRONO
                self.connected = False
                logger.info("🔌 Client OPC UA disconnesso")
                
        except Exception as e:
            logger.error(f"Errore disconnessione: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Restituisce statistiche operative del client.
        
        Returns:
            Dict: Statistiche di funzionamento
        """
        success_rate = 0
        if self.stats['total_readings'] > 0:
            success_rate = (self.stats['successful_readings'] / self.stats['total_readings']) * 100
        
        return {
            **self.stats,
            'success_rate': success_rate,
            'connected': self.connected,
            'buffer_size': len(self.data_buffer),
            'sensors_mapped': len(self.sensor_nodes)
        }

# =============================================================================
# ISTANZA GLOBALE CLIENT
# =============================================================================

# Crea istanza globale del client OPC UA
opc_client = IndustrialOPCClient()

# =============================================================================
# TEST MODULE (SOLO PER DEBUG)
# =============================================================================

if __name__ == "__main__":
    """
    Test delle funzionalità del client OPC UA (VERSIONE SINCRONA).
    """
    def test_client():
        print("🧪 Test Client OPC UA (Sincrono)")
        print("================================")
        
        # Test connessione
        print("Tentativo connessione...")
        if opc_client.connect():  # SINCRONO
            print("✅ Connessione riuscita")
            
            # Test discovery
            print("Discovery nodi sensori...")
            if opc_client.discover_sensor_nodes():  # SINCRONO
                print("✅ Nodi sensori trovati")
                
                # Test lettura dati
                print("Lettura dati sensori...")
                readings = opc_client.read_sensor_data()  # SINCRONO
                
                if readings:
                    print(f"✅ Letti {len(readings)} sensori:")
                    for reading in readings:
                        print(f"  - {reading['sensor_type']}: {reading['value']:.2f} {reading['unit']}")
                else:
                    print("❌ Nessun dato letto")
            else:
                print("❌ Discovery fallita")
            
            # Disconnessione
            opc_client.disconnect()  # SINCRONO
        else:
            print("❌ Connessione fallita")
        
        # Statistiche finali
        stats = opc_client.get_statistics()
        print(f"\n📊 Statistiche: {stats}")
    
    # Esegue il test sincrono
    test_client()