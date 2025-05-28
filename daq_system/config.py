# config.py - Configurazioni centrali per il sistema DAQ
"""
Questo modulo centralizza tutte le configurazioni del sistema.
Separare le configurazioni dal codice è una best practice che permette:
- Facile modifica parametri senza toccare il codice
- Configurazioni diverse per sviluppo/produzione
- Maggiore sicurezza (password non hardcoded)
"""

import os
from dataclasses import dataclass
from typing import Dict, Any
from decouple import config

# =============================================================================
# CONFIGURAZIONI DATABASE TIMESCALEDB
# =============================================================================

@dataclass
class DatabaseConfig:
    """
    Configurazioni per la connessione a TimescaleDB.
    Utilizziamo dataclass per avere una struttura pulita e type hints.
    """
    # Parametri connessione database
    host: str = config('DB_HOST', default='localhost')
    port: int = config('DB_PORT', default=5431, cast=int)  # Porta personalizzata 5431
    database: str = config('DB_NAME', default='industrial_iot')
    username: str = config('DB_USER', default='iot_user')
    password: str = config('DB_PASSWORD', default='iot_password')
    
    # Pool di connessioni per performance
    min_connections: int = config('DB_MIN_CONN', default=2, cast=int)
    max_connections: int = config('DB_MAX_CONN', default=10, cast=int)
    
    # Timeout connessioni
    connection_timeout: int = config('DB_TIMEOUT', default=30, cast=int)
    
    def get_connection_string(self) -> str:
        """
        Costruisce la stringa di connessione PostgreSQL.
        Format: postgresql://user:password@host:port/database
        """
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

# =============================================================================
# CONFIGURAZIONI SERVER OPC UA
# =============================================================================

@dataclass
class OPCServerConfig:
    """
    Configurazioni per il server OPC UA che simula i sensori industriali.
    """
    # Endpoint del server OPC UA
    endpoint: str = config('OPC_ENDPOINT', default='opc.tcp://localhost:4840')
    
    # Namespace e identificatori nodi
    namespace_uri: str = "http://industrial-iot-demo.com"
    namespace_index: int = 2
    
    # Configurazioni sensori simulati
    sensors: Dict[str, Dict[str, Any]] = None
    
    def __post_init__(self):
        """
        Inizializza la configurazione sensori dopo la creazione dell'oggetto.
        __post_init__ viene chiamato automaticamente dalle dataclass.
        """
        if self.sensors is None:
            # Definisce i sensori da simulare con i loro parametri
            self.sensors = {
                "temperature": {
                    "node_id": f"ns={self.namespace_index};s=Temperature",
                    "name": "Temperature Sensor",
                    "unit": "°C",
                    "min_value": 15.0,
                    "max_value": 45.0,
                    "base_value": 25.0,
                    "noise_factor": 2.0,  # Variazione casuale ±2°C
                    "update_interval": 2.0  # Aggiornamento ogni 2 secondi
                },
                "pressure": {
                    "node_id": f"ns={self.namespace_index};s=Pressure",
                    "name": "Pressure Sensor", 
                    "unit": "bar",
                    "min_value": 0.8,
                    "max_value": 2.5,
                    "base_value": 1.2,
                    "noise_factor": 0.1,  # Variazione ±0.1 bar
                    "update_interval": 2.0
                },
                "vibration": {
                    "node_id": f"ns={self.namespace_index};s=Vibration",
                    "name": "Vibration Sensor",
                    "unit": "mm/s", 
                    "min_value": 0.1,
                    "max_value": 3.0,
                    "base_value": 0.8,
                    "noise_factor": 0.2,  # Variazione ±0.2 mm/s
                    "update_interval": 2.0
                }
            }

# =============================================================================
# CONFIGURAZIONI SISTEMA DAQ
# =============================================================================

@dataclass 
class DAQConfig:
    """
    Configurazioni per il sistema di acquisizione dati (DAQ).
    """
    # Identificativo della macchina/impianto
    machine_id: str = config('MACHINE_ID', default='MACHINE_001')
    location: str = config('LOCATION', default='Plant_A_Line_1')
    
    # Timing acquisizione dati
    acquisition_interval: float = config('ACQ_INTERVAL', default=5.0, cast=float)  # secondi
    batch_size: int = config('BATCH_SIZE', default=10, cast=int)  # numero campioni per batch
    
    # Soglie per rilevamento anomalie
    temperature_max: float = config('TEMP_MAX', default=40.0, cast=float)  # °C
    temperature_min: float = config('TEMP_MIN', default=18.0, cast=float)  # °C
    pressure_max: float = config('PRESS_MAX', default=2.0, cast=float)     # bar
    pressure_min: float = config('PRESS_MIN', default=0.9, cast=float)     # bar
    vibration_max: float = config('VIB_MAX', default=2.5, cast=float)      # mm/s
    
    # Configurazioni qualità segnale
    min_quality_threshold: int = config('MIN_QUALITY', default=80, cast=int)  # %
    
    # Buffer per gestione disconnessioni temporanee
    max_buffer_size: int = config('MAX_BUFFER', default=1000, cast=int)

# =============================================================================
# CONFIGURAZIONI LOGGING
# =============================================================================

@dataclass
class LoggingConfig:
    """
    Configurazioni per il sistema di logging.
    """
    # Livello di log (DEBUG, INFO, WARNING, ERROR)
    level: str = config('LOG_LEVEL', default='INFO')
    
    # File di log
    log_file: str = config('LOG_FILE', default='logs/industrial_iot.log')
    
    # Rotazione log
    max_file_size: str = config('LOG_MAX_SIZE', default='10 MB')
    backup_count: int = config('LOG_BACKUP_COUNT', default=5, cast=int)  # Solo numero per loguru
    
    # Formato log
    format_string: str = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"

# =============================================================================
# CONFIGURAZIONE PRINCIPALE
# =============================================================================

class Config:
    """
    Classe principale che aggrega tutte le configurazioni.
    Pattern Singleton per avere una configurazione globale.
    """
    _instance = None
    
    def __new__(cls):
        """
        Implementa pattern Singleton - una sola istanza della configurazione.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """
        Inizializza le configurazioni solo al primo accesso.
        """
        if not self._initialized:
            # Crea le configurazioni specifiche
            self.database = DatabaseConfig()
            self.opc_server = OPCServerConfig() 
            self.daq = DAQConfig()
            self.logging = LoggingConfig()
            
            # Flag per evitare re-inizializzazione
            self._initialized = True
            
            # Crea directory per log se non esiste
            os.makedirs(os.path.dirname(self.logging.log_file), exist_ok=True)
    
    def validate(self) -> bool:
        """
        Valida che tutte le configurazioni siano corrette.
        Utile per catch errori di configurazione all'avvio.
        """
        try:
            # Valida configurazioni database
            assert self.database.host, "Host database non configurato"
            assert 1 <= self.database.port <= 65535, "Porta database non valida"
            assert self.database.database, "Nome database non configurato"
            
            # Valida configurazioni OPC UA
            assert self.opc_server.endpoint.startswith('opc.tcp://'), "Endpoint OPC UA non valido"
            
            # Valida configurazioni DAQ
            assert self.daq.acquisition_interval > 0, "Intervallo acquisizione deve essere positivo"
            assert self.daq.batch_size > 0, "Batch size deve essere positivo"
            
            print("✅ Tutte le configurazioni sono valide")
            return True
            
        except AssertionError as e:
            print(f"❌ Errore configurazione: {e}")
            return False
        except Exception as e:
            print(f"❌ Errore validazione configurazioni: {e}")
            return False

# =============================================================================
# ISTANZA GLOBALE CONFIGURAZIONE
# =============================================================================

# Crea istanza globale della configurazione
# Può essere importata da altri moduli con: from config import settings
settings = Config()

# Valida configurazioni all'import del modulo
if __name__ == "__main__":
    # Test delle configurazioni quando lanciato direttamente
    print("🔧 Test configurazioni sistema...")
    print(f"Database: {settings.database.get_connection_string()}")
    print(f"OPC Server: {settings.opc_server.endpoint}")
    print(f"Machine ID: {settings.daq.machine_id}")
    print(f"Log Level: {settings.logging.level}")
    
    # Valida tutte le configurazioni
    settings.validate()