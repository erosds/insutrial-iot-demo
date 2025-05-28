-- Script di inizializzazione per TimescaleDB
-- Questo script viene eseguito automaticamente al primo avvio del container

-- Abilita l'estensione TimescaleDB su PostgreSQL
-- TimescaleDB aggiunge funzionalità specifiche per time-series
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Crea la tabella per i dati dei sensori industriali
-- Struttura ottimizzata per dati IoT con timestamp, identificatori e valori sensori
CREATE TABLE IF NOT EXISTS sensor_data (
    -- Timestamp con timezone - chiave primaria per partizionamento temporale
    time TIMESTAMPTZ NOT NULL,
    
    -- Identificatori per organizzare i dati
    machine_id TEXT NOT NULL,           -- ID univoco della macchina/impianto
    sensor_type TEXT NOT NULL,          -- Tipo sensore: temperature, pressure, vibration
    location TEXT NOT NULL,             -- Ubicazione fisica del sensore
    
    -- Valori dei sensori
    value DOUBLE PRECISION NOT NULL,    -- Valore principale del sensore
    unit TEXT NOT NULL,                 -- Unità di misura (°C, bar, mm/s)
    
    -- Metadati aggiuntivi per diagnostica
    quality INTEGER DEFAULT 100,        -- Qualità del segnale (0-100%)
    status TEXT DEFAULT 'OK',           -- Stato sensore: OK, WARNING, ERROR
    
    -- Constraint per garantire coerenza dati
    CHECK (quality >= 0 AND quality <= 100),
    CHECK (status IN ('OK', 'WARNING', 'ERROR'))
);

-- Converte la tabella normale in una "hypertable" TimescaleDB
-- Questo abilita il partizionamento automatico basato sul tempo
-- I dati vengono organizzati in "chunks" temporali per performance ottimali
SELECT create_hypertable('sensor_data', 'time', 
    chunk_time_interval => INTERVAL '1 hour'  -- Un chunk ogni ora
);

-- Crea indici per ottimizzare le query più comuni nell'IoT industriale

-- Indice per query per macchina specifica ordinato per tempo (più recente prima)
CREATE INDEX IF NOT EXISTS idx_machine_time 
ON sensor_data (machine_id, time DESC);

-- Indice per query per tipo di sensore e tempo
CREATE INDEX IF NOT EXISTS idx_sensor_type_time 
ON sensor_data (sensor_type, time DESC);

-- Indice per query per ubicazione
CREATE INDEX IF NOT EXISTS idx_location_time 
ON sensor_data (location, time DESC);

-- Indice composito per query analitiche complesse
CREATE INDEX IF NOT EXISTS idx_machine_sensor_time 
ON sensor_data (machine_id, sensor_type, time DESC);

-- Configura la compressione automatica per ottimizzare storage
-- I dati più vecchi di 1 giorno vengono compressi automaticamente
ALTER TABLE sensor_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'machine_id, sensor_type',
    timescaledb.compress_orderby = 'time DESC'
);

-- Abilita la compressione automatica per chunks più vecchi di 1 giorno
SELECT add_compression_policy('sensor_data', INTERVAL '1 day');

-- Politica di retention: elimina automaticamente dati più vecchi di 30 giorni
-- Utile per gestire storage in ambienti industriali con grandi volumi
SELECT add_retention_policy('sensor_data', INTERVAL '30 days');

-- Crea vista materializzata per metriche aggregate comuni
-- Le viste materializzate pre-calcolano risultati per query frequenti
CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_sensor_stats AS
SELECT 
    time_bucket('1 hour', time) as hour,  -- Raggruppa per ore
    machine_id,
    sensor_type,
    location,
    -- Statistiche aggregate per ogni ora
    AVG(value) as avg_value,
    MIN(value) as min_value,
    MAX(value) as max_value,
    COUNT(*) as sample_count,
    -- Calcola percentuale di campioni con qualità alta
    AVG(CASE WHEN quality >= 90 THEN 1.0 ELSE 0.0 END) * 100 as quality_percentage
FROM sensor_data
GROUP BY hour, machine_id, sensor_type, location
ORDER BY hour DESC;

-- Crea indice sulla vista materializzata per query rapide
CREATE INDEX IF NOT EXISTS idx_hourly_stats_time 
ON hourly_sensor_stats (hour DESC);

-- Configura aggiornamento automatico della vista ogni 15 minuti
-- Questo mantiene le statistiche sempre aggiornate
SELECT add_continuous_aggregate_policy('hourly_sensor_stats',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '15 minutes',
    schedule_interval => INTERVAL '15 minutes');

-- Inserisci alcuni dati di esempio per testare il sistema
-- Questi dati simulano sensori di una macchina industriale
INSERT INTO sensor_data (time, machine_id, sensor_type, location, value, unit, quality, status) VALUES 
-- Sensore temperatura
(NOW() - INTERVAL '5 minutes', 'MACHINE_001', 'temperature', 'Plant_A_Line_1', 25.5, '°C', 98, 'OK'),
(NOW() - INTERVAL '4 minutes', 'MACHINE_001', 'temperature', 'Plant_A_Line_1', 26.1, '°C', 97, 'OK'),
(NOW() - INTERVAL '3 minutes', 'MACHINE_001', 'temperature', 'Plant_A_Line_1', 25.8, '°C', 99, 'OK'),

-- Sensore pressione
(NOW() - INTERVAL '5 minutes', 'MACHINE_001', 'pressure', 'Plant_A_Line_1', 1.23, 'bar', 95, 'OK'),
(NOW() - INTERVAL '4 minutes', 'MACHINE_001', 'pressure', 'Plant_A_Line_1', 1.25, 'bar', 94, 'OK'),
(NOW() - INTERVAL '3 minutes', 'MACHINE_001', 'pressure', 'Plant_A_Line_1', 1.21, 'bar', 96, 'OK'),

-- Sensore vibrazione
(NOW() - INTERVAL '5 minutes', 'MACHINE_001', 'vibration', 'Plant_A_Line_1', 0.85, 'mm/s', 92, 'OK'),
(NOW() - INTERVAL '4 minutes', 'MACHINE_001', 'vibration', 'Plant_A_Line_1', 0.91, 'mm/s', 91, 'WARNING'),
(NOW() - INTERVAL '3 minutes', 'MACHINE_001', 'vibration', 'Plant_A_Line_1', 0.78, 'mm/s', 93, 'OK');

-- Aggiorna le statistiche aggregate
REFRESH MATERIALIZED VIEW hourly_sensor_stats;

-- Log di completamento inizializzazione
DO $$
BEGIN
    RAISE NOTICE 'Database TimescaleDB inizializzato con successo!';
    RAISE NOTICE 'Hypertable sensor_data creata con partizionamento orario';
    RAISE NOTICE 'Compressione automatica configurata (1 giorno)';
    RAISE NOTICE 'Retention automatica configurata (30 giorni)';
    RAISE NOTICE 'Vista materializzata hourly_sensor_stats creata';
    RAISE NOTICE 'Dati di esempio inseriti per testing';
END $$;