# opc_server.py - Server OPC UA simulato per sensori industriali
"""
Questo modulo implementa un server OPC UA che simula sensori industriali.
OPC UA è lo standard de facto per comunicazioni industriali IoT.
Il server espone nodi sensori con valori che cambiano realisticamente nel tempo.
"""

import time
import math
import random
import sys
import os
import threading
from datetime import datetime
from typing import Dict, Any
import signal

# Libreria OPC UA Python (versione sincrona per stabilità)
from opcua import Server, ua
from loguru import logger

# Aggiunge il path del progetto per gli import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurazioni locali
from daq_system.config import settings

# =============================================================================
# CLASSE SERVER OPC UA INDUSTRIALE (VERSIONE SINCRONA)
# =============================================================================

class IndustrialOPCServer:
    """
    Server OPC UA che simula sensori di una macchina industriale.
    Espone nodi per temperatura, pressione e vibrazione con valori realistici.
    Versione sincrona per maggiore stabilità.
    """
    
    def __init__(self):
        """
        Inizializza il server OPC UA con configurazioni da config.py
        """
        self.server = None
        self.namespace_index = None
        
        # Dizionario per memorizzare i nodi sensori
        self.sensor_nodes: Dict[str, Any] = {}
        
        # Flag per controllo ciclo principale
        self.running = False
        
        # Thread per aggiornamento sensori
        self.update_thread = None
        
        # Parametri per simulazione realistica
        self.simulation_params = {
            'start_time': datetime.now(),
            'cycle_duration': 300,  # Ciclo simulazione di 5 minuti
        }
        
        logger.info("IndustrialOPCServer inizializzato")
    
    def setup_server(self):
        """
        Configura il server OPC UA con endpoint, namespace e certificati.
        """
        try:
            # Crea istanza server OPC UA
            self.server = Server()
            
            # Configura endpoint (indirizzo di connessione)
            self.server.set_endpoint(settings.opc_server.endpoint)
            logger.info(f"Endpoint configurato: {settings.opc_server.endpoint}")
            
            # Configura nome server (visibile nei client)
            self.server.set_server_name("Industrial IoT Demo Server")
            
            # Registra namespace personalizzato per i nostri nodi
            self.namespace_index = self.server.register_namespace(settings.opc_server.namespace_uri)
            logger.info(f"Namespace registrato: Index {self.namespace_index}")
            
            # Configura politiche di sicurezza (per semplicità, solo None/Anonymous)
            self.server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
            
            logger.success("Server OPC UA configurato correttamente")
            
        except Exception as e:
            logger.error(f"Errore configurazione server: {e}")
            raise
    
    def create_sensor_nodes(self):
        """
        Crea la struttura ad albero dei nodi sensori nel namespace OPC UA.
        Ogni sensore ha nodi per valore, unità, qualità e timestamp.
        """
        try:
            # Ottiene il nodo root del namespace (punto di partenza)
            root_node = self.server.get_objects_node()
            
            # Crea cartella principale per la macchina industriale
            machine_folder = root_node.add_folder(
                self.namespace_index, 
                f"Machine_{settings.daq.machine_id}"
            )
            
            # Crea cartella per i sensori dentro la macchina
            sensors_folder = machine_folder.add_folder(self.namespace_index, "Sensors")
            
            # Itera sui sensori configurati e crea i nodi OPC UA
            for sensor_name, sensor_config in settings.opc_server.sensors.items():
                logger.info(f"Creando nodi per sensore: {sensor_name}")
                
                # Crea cartella specifica per questo sensore
                sensor_folder = sensors_folder.add_folder(
                    self.namespace_index, 
                    sensor_config['name']
                )
                
                # Nodo principale: valore del sensore (variabile)
                # Questo è il nodo che leggeranno i client DAQ
                value_node = sensor_folder.add_variable(
                    self.namespace_index,
                    "Value",
                    sensor_config['base_value'],  # Valore iniziale
                    ua.VariantType.Double         # Tipo di dato: numero decimale
                )
                # Rende il nodo scrivibile (per simulazioni avanzate)
                value_node.set_writable()
                
                # Nodo per unità di misura (proprietà statica)
                unit_node = sensor_folder.add_property(
                    self.namespace_index,
                    "Unit",
                    sensor_config['unit'],
                    ua.VariantType.String
                )
                
                # Nodo per qualità del segnale (0-100%)
                quality_node = sensor_folder.add_variable(
                    self.namespace_index,
                    "Quality",
                    100,  # Qualità iniziale perfetta
                    ua.VariantType.Int32
                )
                quality_node.set_writable()
                
                # Nodo per timestamp ultima lettura
                timestamp_node = sensor_folder.add_variable(
                    self.namespace_index,
                    "Timestamp",
                    datetime.now(),
                    ua.VariantType.DateTime
                )
                timestamp_node.set_writable()
                
                # Nodo per stato sensore (OK, WARNING, ERROR)
                status_node = sensor_folder.add_variable(
                    self.namespace_index,
                    "Status",
                    "OK",
                    ua.VariantType.String
                )
                status_node.set_writable()
                
                # Memorizza i nodi per accesso rapido durante la simulazione
                self.sensor_nodes[sensor_name] = {
                    'config': sensor_config,
                    'value_node': value_node,
                    'quality_node': quality_node,
                    'timestamp_node': timestamp_node,
                    'status_node': status_node,
                    'current_value': sensor_config['base_value']
                }
                
                logger.success(f"Nodi creati per {sensor_name}: Value, Quality, Timestamp, Status")
            
            logger.success(f"Creati {len(self.sensor_nodes)} sensori con struttura completa")
            
        except Exception as e:
            logger.error(f"Errore creazione nodi sensori: {e}")
            raise
    
    def calculate_realistic_value(self, sensor_name: str) -> tuple:
        """
        Calcola valori realistici per i sensori basandosi su modelli matematici.
        Combina trend ciclici, rumore casuale e anomalie occasionali.
        
        Args:
            sensor_name: Nome del sensore (temperature, pressure, vibration)
            
        Returns:
            tuple: (valore, qualità, stato)
        """
        config = self.sensor_nodes[sensor_name]['config']
        
        # Calcola offset temporale in secondi dall'inizio
        time_offset = (datetime.now() - self.simulation_params['start_time']).total_seconds()
        
        # Componente ciclica: simula cicli produttivi (trend sinusoidale)
        cycle_factor = math.sin(2 * math.pi * time_offset / self.simulation_params['cycle_duration'])
        
        # Componente trend a lungo termine (crescita/decrescita lenta)
        trend_factor = 0.1 * math.sin(2 * math.pi * time_offset / (self.simulation_params['cycle_duration'] * 4))
        
        # Rumore casuale per realismo
        noise = random.uniform(-1, 1) * config['noise_factor']
        
        # Calcola valore base con tutti i fattori
        calculated_value = (
            config['base_value'] + 
            (cycle_factor * config['noise_factor'] * 2) +  # Variazione ciclica
            (trend_factor * config['noise_factor']) +      # Trend lento
            noise                                          # Rumore casuale
        )
        
        # Applica limiti realistici per il tipo di sensore
        calculated_value = max(config['min_value'], 
                             min(config['max_value'], calculated_value))
        
        # Calcola qualità del segnale (degrada nel tempo con eventi casuali)
        base_quality = 100
        
        # Degrado casuale qualità (simula interferenze)
        if random.random() < 0.05:  # 5% probabilità di degrado
            quality_loss = random.randint(10, 30)
            base_quality -= quality_loss
        
        # Qualità leggermente più bassa per valori estremi
        value_range = config['max_value'] - config['min_value'] 
        value_position = (calculated_value - config['min_value']) / value_range
        if value_position < 0.1 or value_position > 0.9:  # Valori agli estremi
            base_quality -= random.randint(5, 15)
        
        quality = max(70, min(100, base_quality))  # Qualità tra 70-100%
        
        # Determina stato sensore basato su valore e qualità
        if quality < 80:
            status = "WARNING"
        elif calculated_value > config['max_value'] * 0.9 or calculated_value < config['min_value'] * 1.1:
            status = "WARNING" if random.random() < 0.3 else "OK"
        else:
            status = "OK"
        
        # Occasionalmente simula errori sensore
        if random.random() < 0.001:  # 0.1% probabilità errore
            status = "ERROR"
            quality = random.randint(0, 50)
        
        return calculated_value, quality, status
    
    def update_sensor_values(self):
        """
        Loop che aggiorna continuamente i valori dei sensori (versione sincrona).
        Questo metodo simula il comportamento di sensori reali.
        """
        logger.info("Avvio aggiornamento continuo sensori...")
        
        while self.running:
            try:
                current_time = datetime.now()
                
                # Aggiorna ogni sensore
                for sensor_name, sensor_info in self.sensor_nodes.items():
                    # Calcola nuovo valore realistico
                    new_value, quality, status = self.calculate_realistic_value(sensor_name)
                    
                    # Aggiorna i nodi OPC UA con i nuovi valori
                    sensor_info['value_node'].set_value(new_value)
                    sensor_info['quality_node'].set_value(quality)
                    sensor_info['status_node'].set_value(status)
                    sensor_info['timestamp_node'].set_value(current_time)
                    
                    # Memorizza valore corrente per log
                    sensor_info['current_value'] = new_value
                    
                    # Log dettagliato per debugging (solo ogni 20 secondi)
                    if int(current_time.timestamp()) % 20 == 0:
                        logger.debug(f"{sensor_name}: {new_value:.2f} {sensor_info['config']['unit']} "
                                   f"(Q:{quality}%, S:{status})")
                
                # Log riassuntivo periodico (ogni minuto)
                if int(current_time.timestamp()) % 60 == 0:
                    values_summary = {
                        name: f"{info['current_value']:.2f}{info['config']['unit']}"
                        for name, info in self.sensor_nodes.items()
                    }
                    logger.info(f"Sensori attivi: {values_summary}")
                
                # Attende prima del prossimo aggiornamento
                time.sleep(2.0)
                
            except Exception as e:
                logger.error(f"Errore aggiornamento sensori: {e}")
                time.sleep(5.0)  # Attesa più lunga in caso di errore
    
    def start_server(self):
        """
        Avvia il server OPC UA e inizia la simulazione sensori (versione sincrona).
        """
        try:
            # Configura il server
            self.setup_server()
            
            # Crea struttura nodi sensori
            self.create_sensor_nodes()
            
            # Avvia il server OPC UA
            self.server.start()
            logger.success(f"🚀 Server OPC UA avviato su {settings.opc_server.endpoint}")
            logger.info(f"📊 Sensori attivi: {list(self.sensor_nodes.keys())}")
            
            # Abilita flag per loop aggiornamenti
            self.running = True
            
            # Avvia thread per aggiornamento sensori
            self.update_thread = threading.Thread(target=self.update_sensor_values)
            self.update_thread.daemon = True
            self.update_thread.start()
            
            logger.info("✅ Server completamente operativo - in attesa connessioni client...")
            
            # Loop principale - mantiene il server attivo
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Interruzione da tastiera ricevuta")
            
        except Exception as e:
            logger.error(f"Errore avvio server: {e}")
            raise
    
    def stop_server(self):
        """
        Ferma il server OPC UA in modo pulito.
        """
        logger.info("🛑 Arresto server OPC UA...")
        
        # Ferma loop aggiornamenti
        self.running = False
        
        # Attende che il thread finisca
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=5)
        
        # Ferma il server
        if self.server:
            self.server.stop()
            
        logger.success("Server OPC UA fermato correttamente")

# =============================================================================
# GESTIONE SEGNALI E AVVIO PRINCIPALE
# =============================================================================

# Istanza globale del server
opc_server = None

def signal_handler(signum, frame):
    """
    Gestisce i segnali di sistema per arresto pulito.
    """
    logger.info(f"Ricevuto segnale {signum} - arresto in corso...")
    
    if opc_server and opc_server.running:
        opc_server.stop_server()
    
    sys.exit(0)

def main():
    """
    Funzione principale per avvio del server OPC UA.
    """
    global opc_server
    
    # Configura gestione segnali
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Crea e avvia il server
        opc_server = IndustrialOPCServer()
        opc_server.start_server()
        
    except KeyboardInterrupt:
        logger.info("Interruzione da tastiera ricevuta")
    except Exception as e:
        logger.error(f"Errore critico: {e}")
    finally:
        # Cleanup finale
        if opc_server:
            opc_server.stop_server()

# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    """
    Entry point principale - avvia il server OPC UA quando eseguito direttamente.
    """
    print("🏭 Industrial OPC UA Server Demo")
    print("================================")
    print(f"Endpoint: {settings.opc_server.endpoint}")
    print(f"Namespace: {settings.opc_server.namespace_uri}")
    print(f"Sensori configurati: {len(settings.opc_server.sensors)}")
    print("\nPremi Ctrl+C per fermare il server\n")
    
    # Avvia il server
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Server fermato dall'utente")
    except Exception as e:
        print(f"\n❌ Errore fatale: {e}")
        sys.exit(1)
# =============================================================================

if __name__ == "__main__":
    """
    Entry point principale - avvia il server OPC UA quando eseguito direttamente.
    """
    print("🏭 Industrial OPC UA Server Demo")
    print("================================")
    print(f"Endpoint: {settings.opc_server.endpoint}")
    print(f"Namespace: {settings.opc_server.namespace_uri}")
    print(f"Sensori configurati: {len(settings.opc_server.sensors)}")
    print("\nPremi Ctrl+C per fermare il server\n")
    
    # Avvia il server
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Server fermato dall'utente")
    except Exception as e:
        print(f"\n❌ Errore fatale: {e}")
        sys.exit(1)


# =============================================================================
# GESTIONE SEGNALI E AVVIO PRINCIPALE
# =============================================================================

# Istanza globale del server
opc_server = None

def signal_handler(signum, frame):
    """
    Gestisce i segnali di sistema (Ctrl+C) per arresto pulito.
    """
    logger.info(f"Ricevuto segnale {signum} - arresto in corso...")
    
    # Ferma il server se attivo
    if opc_server and opc_server.running:
        asyncio.create_task(opc_server.stop_server())
    
    sys.exit(0)

async def main():
    """
    Funzione principale asincrona per avvio del server OPC UA.
    """
    global opc_server
    
    # Configura gestione segnali per arresto pulito
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Crea e avvia il server
        opc_server = IndustrialOPCServer()
        await opc_server.start_server()
        
    except KeyboardInterrupt:
        logger.info("Interruzione da tastiera ricevuta")
    except Exception as e:
        logger.error(f"Errore critico: {e}")
    finally:
        # Cleanup finale
        if opc_server:
            await opc_server.stop_server()
