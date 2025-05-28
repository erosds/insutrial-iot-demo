# database.py - Gestione della connessione e operazioni TimescaleDB
"""
Questo modulo gestisce tutte le interazioni con TimescaleDB.
Include connessione, inserimento dati, query e gestione errori.
Separando la logica database si ottiene maggiore manutenibilità e testabilità.
"""

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import pandas as pd
import sys
import os
from loguru import logger

# Aggiunge il path del progetto per gli import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from daq_system.config import settings

# =============================================================================
# CLASSE PRINCIPALE DATABASE MANAGER
# =============================================================================

class TimescaleDBManager:
    """
    Gestore principale per tutte le operazioni su TimescaleDB.
    Implementa pattern Singleton e connection pooling per performance ottimali.
    """
    
    _instance = None
    _connection_pool = None
    
    def __new__(cls):
        """
        Pattern Singleton: garantisce una sola istanza del database manager.
        Importante per evitare connessioni multiple non necessarie.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """
        Inizializza il connection pool solo al primo accesso.
        """
        if not self._initialized:
            self._setup_connection_pool()
            self._initialized = True
            logger.info("TimescaleDB Manager inizializzato")
    
    def _setup_connection_pool(self):
        """
        Crea il pool di connessioni per gestire multiple connessioni simultanee.
        Il connection pooling è fondamentale per applicazioni multi-thread.
        """
        try:
            # Crea connection pool con parametri da configurazione
            self._connection_pool = ThreadedConnectionPool(
                minconn=settings.database.min_connections,    # Connessioni minime sempre aperte
                maxconn=settings.database.max_connections,    # Massimo connessioni simultanee
                host=settings.database.host,
                port=settings.database.port,
                database=settings.database.database,
                user=settings.database.username,
                password=settings.database.password,
                # Parametri specifici PostgreSQL/TimescaleDB
                connect_timeout=settings.database.connection_timeout,
                application_name="Industrial_IoT_DAQ",        # Nome app nei log DB
                # Ottimizzazioni per time-series
                options="-c timezone=UTC"                     # Forza UTC per consistency
            )
            
            logger.success(f"Connection pool creato: {settings.database.min_connections}-{settings.database.max_connections} connessioni")
            
        except Exception as e:
            logger.error(f"Errore creazione connection pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """
        Context manager per ottenere connessioni dal pool.
        Garantisce che le connessioni vengano sempre rilasciate.
        
        Uso: 
        with db_manager.get_connection() as conn:
            # usa connessione
            pass
        # connessione automaticamente rilasciata
        """
        connection = None
        try:
            # Ottiene connessione dal pool
            connection = self._connection_pool.getconn()
            if connection:
                yield connection
            else:
                raise Exception("Impossibile ottenere connessione dal pool")
                
        except Exception as e:
            logger.error(f"Errore connessione database: {e}")
            # In caso di errore, rollback transazione
            if connection:
                connection.rollback()
            raise
            
        finally:
            # Rilascia sempre la connessione al pool
            if connection:
                self._connection_pool.putconn(connection)
    
    def test_connection(self) -> bool:
        """
        Testa la connessione al database e verifica l'estensione TimescaleDB.
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Test connessione base
                    cursor.execute("SELECT version();")
                    pg_version = cursor.fetchone()[0]
                    logger.info(f"PostgreSQL: {pg_version}")
                    
                    # Verifica TimescaleDB extension
                    cursor.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';")
                    result = cursor.fetchone()
                    if result:
                        logger.info(f"TimescaleDB extension: {result[1]}")
                        return True
                    else:
                        logger.error("TimescaleDB extension non trovata!")
                        return False
                        
        except Exception as e:
            logger.error(f"Test connessione fallito: {e}")
            return False

# =============================================================================
# CLASSE SPECIALIZZATA PER DATI SENSORI
# =============================================================================

class SensorDataManager:
    """
    Classe specializzata per gestire i dati dei sensori industriali.
    Si occupa di inserimenti, query e aggregazioni specifiche per IoT.
    """
    
    def __init__(self, db_manager: TimescaleDBManager):
        """
        Inizializza con riferimento al database manager.
        """
        self.db_manager = db_manager
        logger.info("SensorDataManager inizializzato")
    
    def insert_sensor_reading(self, 
                            machine_id: str,
                            sensor_type: str,
                            location: str,
                            value: float,
                            unit: str,
                            quality: int = 100,
                            status: str = 'OK',
                            timestamp: Optional[datetime] = None) -> bool:
        """
        Inserisce una singola lettura sensore nel database.
        
        Args:
            machine_id: Identificativo macchina
            sensor_type: Tipo sensore (temperature, pressure, vibration)
            location: Ubicazione fisica
            value: Valore misurato
            unit: Unità di misura
            quality: Qualità segnale (0-100%)
            status: Stato sensore (OK, WARNING, ERROR)
            timestamp: Timestamp della misura (default: ora corrente)
            
        Returns:
            bool: True se inserimento riuscito
        """
        try:
            # Se timestamp non specificato, usa ora corrente UTC
            if timestamp is None:
                timestamp = datetime.now(timezone.utc)
            
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Query preparata per sicurezza (previene SQL injection)
                    insert_query = """
                        INSERT INTO sensor_data 
                        (time, machine_id, sensor_type, location, value, unit, quality, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    
                    # Esegue l'inserimento
                    cursor.execute(insert_query, (
                        timestamp, machine_id, sensor_type, location,
                        value, unit, quality, status
                    ))
                    
                    # Commit transazione
                    conn.commit()
                    
                    logger.debug(f"Inserito: {machine_id}/{sensor_type} = {value} {unit}")
                    return True
                    
        except Exception as e:
            logger.error(f"Errore inserimento sensor reading: {e}")
            return False
    
    def insert_batch_readings(self, readings: List[Dict[str, Any]]) -> int:
        """
        Inserisce un batch di letture sensori per performance ottimali.
        L'inserimento batch è molto più efficiente per grandi volumi di dati.
        
        Args:
            readings: Lista di dizionari con dati sensori
                      [{'machine_id': 'M1', 'sensor_type': 'temp', ...}, ...]
        
        Returns:
            int: Numero di record inseriti con successo
        """
        if not readings:
            return 0
            
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Prepara dati per inserimento batch
                    insert_data = []
                    for reading in readings:
                        # Aggiunge timestamp se mancante
                        if 'timestamp' not in reading or reading['timestamp'] is None:
                            reading['timestamp'] = datetime.now(timezone.utc)
                        
                        # Valori di default
                        reading.setdefault('quality', 100)
                        reading.setdefault('status', 'OK')
                        
                        # Crea tupla per inserimento
                        insert_data.append((
                            reading['timestamp'],
                            reading['machine_id'],
                            reading['sensor_type'],
                            reading['location'],
                            reading['value'],
                            reading['unit'],
                            reading['quality'],
                            reading['status']
                        ))
                    
                    # Esegue inserimento batch usando execute_values (molto più veloce)
                    psycopg2.extras.execute_values(
                        cursor,
                        """INSERT INTO sensor_data 
                           (time, machine_id, sensor_type, location, value, unit, quality, status)
                           VALUES %s""",
                        insert_data,
                        template=None,
                        page_size=100  # Inserisce 100 record per volta
                    )
                    
                    # Commit transazione
                    conn.commit()
                    
                    inserted_count = len(insert_data)
                    logger.info(f"Inseriti {inserted_count} record in batch")
                    return inserted_count
                    
        except Exception as e:
            logger.error(f"Errore inserimento batch: {e}")
            return 0
    
    def get_latest_readings(self, 
                          machine_id: Optional[str] = None,
                          sensor_type: Optional[str] = None,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """
        Recupera le letture più recenti dei sensori.
        
        Args:
            machine_id: Filtra per macchina specifica (opzionale)
            sensor_type: Filtra per tipo sensore (opzionale)
            limit: Numero massimo di record da restituire
            
        Returns:
            List[Dict]: Lista di letture sensori
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    # Costruisce query dinamicamente in base ai filtri
                    query = "SELECT * FROM sensor_data WHERE 1=1"
                    params = []
                    
                    if machine_id:
                        query += " AND machine_id = %s"
                        params.append(machine_id)
                    
                    if sensor_type:
                        query += " AND sensor_type = %s"
                        params.append(sensor_type)
                    
                    query += " ORDER BY time DESC LIMIT %s"
                    params.append(limit)
                    
                    cursor.execute(query, params)
                    results = cursor.fetchall()
                    
                    # Converte risultati in lista di dizionari
                    return [dict(row) for row in results]
                    
        except Exception as e:
            logger.error(f"Errore recupero latest readings: {e}")
            return []
    
    def get_hourly_stats(self, 
                        machine_id: str,
                        hours_back: int = 24) -> pd.DataFrame:
        """
        Recupera statistiche aggregate orarie per una macchina.
        Utilizza la vista materializzata per performance ottimali.
        
        Args:
            machine_id: ID della macchina
            hours_back: Ore precedenti da considerare
            
        Returns:
            pd.DataFrame: Statistiche aggregate per ora
        """
        try:
            with self.db_manager.get_connection() as conn:
                query = """
                    SELECT 
                        hour,
                        sensor_type,
                        avg_value,
                        min_value,
                        max_value,
                        sample_count,
                        quality_percentage
                    FROM hourly_sensor_stats
                    WHERE machine_id = %s 
                      AND hour >= NOW() - INTERVAL '%s hours'
                    ORDER BY hour DESC, sensor_type
                """
                
                # Usa pandas per leggere direttamente in DataFrame
                df = pd.read_sql(query, conn, params=[machine_id, hours_back])
                
                logger.debug(f"Recuperate {len(df)} righe di statistiche orarie")
                return df
                
        except Exception as e:
            logger.error(f"Errore recupero hourly stats: {e}")
            return pd.DataFrame()  # DataFrame vuoto in caso di errore
    
    def check_anomalies(self, 
                       machine_id: str,
                       minutes_back: int = 30) -> List[Dict[str, Any]]:
        """
        Rileva anomalie nei sensori basandosi su soglie configurate.
        
        Args:
            machine_id: ID macchina da controllare
            minutes_back: Minuti precedenti da analizzare
            
        Returns:
            List[Dict]: Lista di anomalie rilevate
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    # Query per rilevare anomalie basate su soglie configurate
                    query = """
                        SELECT 
                            time,
                            machine_id,
                            sensor_type,
                            value,
                            unit,
                            quality,
                            status,
                            CASE 
                                WHEN sensor_type = 'temperature' AND (value > %s OR value < %s) THEN 'TEMP_OUT_OF_RANGE'
                                WHEN sensor_type = 'pressure' AND (value > %s OR value < %s) THEN 'PRESSURE_OUT_OF_RANGE'
                                WHEN sensor_type = 'vibration' AND value > %s THEN 'HIGH_VIBRATION'
                                WHEN quality < %s THEN 'LOW_QUALITY'
                                WHEN status != 'OK' THEN 'SENSOR_ERROR'
                                ELSE NULL
                            END as anomaly_type
                        FROM sensor_data
                        WHERE machine_id = %s
                          AND time >= NOW() - INTERVAL '%s minutes'
                          AND (
                            (sensor_type = 'temperature' AND (value > %s OR value < %s)) OR
                            (sensor_type = 'pressure' AND (value > %s OR value < %s)) OR
                            (sensor_type = 'vibration' AND value > %s) OR
                            quality < %s OR
                            status != 'OK'
                          )
                        ORDER BY time DESC
                    """
                    
                    # Parametri per le soglie (da configurazione)
                    params = [
                        settings.daq.temperature_max, settings.daq.temperature_min,  # temp soglie per CASE
                        settings.daq.pressure_max, settings.daq.pressure_min,       # pressure soglie per CASE
                        settings.daq.vibration_max,                                 # vibration soglia per CASE
                        settings.daq.min_quality_threshold,                         # quality soglia per CASE
                        machine_id, minutes_back,                                   # WHERE clause
                        settings.daq.temperature_max, settings.daq.temperature_min, # temp soglie per WHERE
                        settings.daq.pressure_max, settings.daq.pressure_min,       # pressure soglie per WHERE
                        settings.daq.vibration_max,                                 # vibration soglia per WHERE
                        settings.daq.min_quality_threshold                          # quality soglia per WHERE
                    ]
                    
                    cursor.execute(query, params)
                    anomalies = cursor.fetchall()
                    
                    result = [dict(row) for row in anomalies]
                    
                    if result:
                        logger.warning(f"Rilevate {len(result)} anomalie per {machine_id}")
                    
                    return result
                    
        except Exception as e:
            logger.error(f"Errore check anomalies: {e}")
            return []
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        Recupera statistiche generali del database per monitoraggio.
        """
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    stats = {}
                    
                    # Conta totale record
                    cursor.execute("SELECT COUNT(*) FROM sensor_data")
                    stats['total_records'] = cursor.fetchone()[0]
                    
                    # Dimensione tabella
                    cursor.execute("""
                        SELECT pg_size_pretty(pg_total_relation_size('sensor_data')) as size
                    """)
                    stats['table_size'] = cursor.fetchone()[0]
                    
                    # Record per macchina
                    cursor.execute("""
                        SELECT machine_id, COUNT(*) as count
                        FROM sensor_data 
                        GROUP BY machine_id
                        ORDER BY count DESC
                    """)
                    stats['records_per_machine'] = cursor.fetchall()
                    
                    # Ultimo aggiornamento
                    cursor.execute("SELECT MAX(time) FROM sensor_data")
                    last_update = cursor.fetchone()[0]
                    stats['last_update'] = last_update.isoformat() if last_update else None
                    
                    logger.info(f"Database stats: {stats['total_records']} records, size: {stats['table_size']}")
                    return stats
                    
        except Exception as e:
            logger.error(f"Errore recupero database stats: {e}")
            return {}

# =============================================================================
# ISTANZE GLOBALI
# =============================================================================

# Crea istanze globali per uso nell'applicazione
db_manager = TimescaleDBManager()
sensor_db = SensorDataManager(db_manager)

# Test delle connessioni all'import del modulo
if __name__ == "__main__":
    print("🔧 Test connessione TimescaleDB...")
    
    if db_manager.test_connection():
        print("✅ Connessione TimescaleDB OK")
        
        # Test inserimento
        print("🧪 Test inserimento dati...")
        test_reading = {
            'machine_id': 'TEST_MACHINE',
            'sensor_type': 'temperature',
            'location': 'test_location', 
            'value': 25.5,
            'unit': '°C'
        }
        
        if sensor_db.insert_sensor_reading(**test_reading):
            print("✅ Test inserimento OK")
            
            # Test recupero
            readings = sensor_db.get_latest_readings(limit=1)
            if readings:
                print(f"✅ Test lettura OK: {readings[0]}")
            
    else:
        print("❌ Connessione TimescaleDB FALLITA")