#!/bin/bash

echo "🔧 Aggiornamento Schema Database Industrial IoT"
echo "==============================================="

# Verifica che docker-compose sia attivo
if ! docker-compose ps | grep -q "timescaledb.*Up"; then
    echo "❌ Container TimescaleDB non attivo!"
    echo "💡 Avvia con: docker-compose up -d"
    exit 1
fi

echo "✅ Container TimescaleDB trovato"

# Salva lo script SQL in un file temporaneo
cat > /tmp/update_schema.sql << 'EOF'
-- Rimuovi constraint esistente
ALTER TABLE sensor_data DROP CONSTRAINT IF EXISTS sensor_data_status_check;

-- Aggiungi nuovo constraint più flessibile
ALTER TABLE sensor_data ADD CONSTRAINT sensor_data_status_check 
CHECK (status IN (
    'OK', 'WARNING', 'ERROR',
    'OUT_OF_RANGE', 'HIGH_VIBRATION', 'LOW_QUALITY', 'RAPID_CHANGE',
    'EXTENDED_RANGE', 'SENSOR_FAULT', 'THRESHOLD_EXCEEDED', 'COMM_ERROR',
    'HIGH_DEVIATION', 'MAINTENANCE_REQUIRED', 'CALIBRATION_NEEDED',
    'NOISE_DETECTED', 'TREND_ANOMALY'
));

-- Inserisci anomalie di test
INSERT INTO sensor_data (time, machine_id, sensor_type, location, value, unit, quality, status) VALUES 
(NOW() - INTERVAL '5 minutes', 'MACHINE_001', 'anomaly', 'Plant_A_Line_1', 4.0, 'severity', 100, 'OUT_OF_RANGE'),
(NOW() - INTERVAL '10 minutes', 'MACHINE_001', 'anomaly', 'Plant_A_Line_1', 4.2, 'severity', 100, 'HIGH_VIBRATION'),
(NOW() - INTERVAL '15 minutes', 'MACHINE_001', 'anomaly', 'Plant_A_Line_1', 2.5, 'severity', 100, 'LOW_QUALITY'),
(NOW() - INTERVAL '20 minutes', 'MACHINE_001', 'anomaly', 'Plant_A_Line_1', 3.1, 'severity', 100, 'RAPID_CHANGE'),
(NOW() - INTERVAL '25 minutes', 'MACHINE_001', 'anomaly', 'Plant_A_Line_1', 2.0, 'severity', 100, 'EXTENDED_RANGE');

-- Verifica risultati
SELECT 'Anomalie create:' as info, COUNT(*) as count
FROM sensor_data 
WHERE sensor_type = 'anomaly' 
  AND time >= NOW() - INTERVAL '30 minutes';
EOF

echo "📝 Esecuzione aggiornamento schema..."

# Esegui lo script nel container
docker-compose exec timescaledb psql -U iot_user -d industrial_iot -f /dev/stdin < /tmp/update_schema.sql

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Schema aggiornato con successo!"
    echo ""
    
    # Verifica che le anomalie siano state create
    echo "🔍 Verifica anomalie create..."
    docker-compose exec timescaledb psql -U iot_user -d industrial_iot -c "
    SELECT 
        status as anomaly_type,
        value as severity,
        ROUND(EXTRACT(EPOCH FROM (NOW() - time))/60, 1) as minutes_ago
    FROM sensor_data 
    WHERE sensor_type = 'anomaly' 
      AND time >= NOW() - INTERVAL '30 minutes'
    ORDER BY time DESC;
    "
    
    echo ""
    echo "🎯 Risultati:"
    echo "✅ Constraint database aggiornato"
    echo "✅ Anomalie di test create"
    echo "✅ Ora puoi eseguire il script Python senza errori"
    echo ""
    echo "📊 Prossimi passi:"
    echo "1. Esegui: python test_anomalies.py"
    echo "2. Controlla Grafana: http://localhost:3000"
    echo "3. Il conteggio anomalie dovrebbe essere > 0"
    
else
    echo "❌ Errore durante aggiornamento schema!"
    exit 1
fi

# Pulisce file temporaneo
rm -f /tmp/update_schema.sql