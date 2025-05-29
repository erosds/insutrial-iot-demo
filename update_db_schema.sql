-- update_db_schema.sql
-- Script per aggiornare il constraint status per supportare più tipi di anomalie

-- 1. RIMUOVI il constraint esistente
ALTER TABLE sensor_data DROP CONSTRAINT IF EXISTS sensor_data_status_check;

-- 2. AGGIUNGI un nuovo constraint più flessibile che include i tipi di anomalia
ALTER TABLE sensor_data ADD CONSTRAINT sensor_data_status_check 
CHECK (status IN (
    -- Status normali dei sensori
    'OK', 
    'WARNING', 
    'ERROR',
    
    -- Tipi specifici di anomalie
    'OUT_OF_RANGE',
    'HIGH_VIBRATION', 
    'LOW_QUALITY',
    'RAPID_CHANGE',
    'EXTENDED_RANGE',
    'SENSOR_FAULT',
    'THRESHOLD_EXCEEDED',
    'COMM_ERROR',
    'HIGH_DEVIATION',
    'MAINTENANCE_REQUIRED',
    'CALIBRATION_NEEDED',
    'NOISE_DETECTED',
    'TREND_ANOMALY'
));

-- 3. VERIFICA che il constraint sia stato aggiornato
SELECT 
    conname as constraint_name,
    consrc as constraint_definition
FROM pg_constraint 
WHERE conname = 'sensor_data_status_check';

-- 4. INSERISCI alcune anomalie di test per verificare che funzioni
INSERT INTO sensor_data (time, machine_id, sensor_type, location, value, unit, quality, status) VALUES 
-- Anomalie di test con i nuovi status
(NOW() - INTERVAL '5 minutes', 'MACHINE_001', 'anomaly', 'Plant_A_Line_1', 4.0, 'severity', 100, 'OUT_OF_RANGE'),
(NOW() - INTERVAL '10 minutes', 'MACHINE_001', 'anomaly', 'Plant_A_Line_1', 4.2, 'severity', 100, 'HIGH_VIBRATION'),
(NOW() - INTERVAL '15 minutes', 'MACHINE_001', 'anomaly', 'Plant_A_Line_1', 2.5, 'severity', 100, 'LOW_QUALITY'),
(NOW() - INTERVAL '20 minutes', 'MACHINE_001', 'anomaly', 'Plant_A_Line_1', 3.1, 'severity', 100, 'RAPID_CHANGE'),
(NOW() - INTERVAL '25 minutes', 'MACHINE_001', 'anomaly', 'Plant_A_Line_1', 2.0, 'severity', 100, 'EXTENDED_RANGE');

-- 5. VERIFICA che le anomalie siano state inserite
SELECT 
    'Anomalie inserite' as info,
    COUNT(*) as count
FROM sensor_data 
WHERE sensor_type = 'anomaly' 
  AND time >= NOW() - INTERVAL '30 minutes';

-- 6. MOSTRA le anomalie create
SELECT 
    time,
    status as anomaly_type,
    value as severity,
    EXTRACT(EPOCH FROM (NOW() - time))/60 as minutes_ago
FROM sensor_data 
WHERE sensor_type = 'anomaly' 
  AND time >= NOW() - INTERVAL '30 minutes'
ORDER BY time DESC;

-- 7. AGGIORNA anche la vista materializzata se necessario
REFRESH MATERIALIZED VIEW hourly_sensor_stats;

-- Messaggio di conferma
DO $$
BEGIN
    RAISE NOTICE '✅ Schema database aggiornato con successo!';
    RAISE NOTICE '🎯 Constraint status ora supporta tipi di anomalia personalizzati';
    RAISE NOTICE '📊 Anomalie di test inserite per verifica Grafana';
END $$;