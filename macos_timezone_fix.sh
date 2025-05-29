#!/bin/bash

echo "🍎 Fix Timezone per macOS Industrial IoT"
echo "========================================"

# 1. Mostra situazione attuale
echo "📊 Situazione Attuale:"
echo "   Sistema macOS: $(date) ($(date +%Z))"
echo "   Sistema UTC: $(date -u)"
echo "   Database ora: $(docker-compose exec timescaledb date)"

# 2. Il problema: il DAQ system sta usando il timezone locale (CEST) invece di UTC
echo ""
echo "🔍 Problema Identificato:"
echo "   ❌ Il sistema DAQ inserisce timestamp in CEST (UTC+2)"
echo "   ❌ Il database è configurato in UTC"
echo "   ❌ Grafana vede dati nel futuro di 2 ore"

# 3. Pulizia dati esistenti con timestamp sbagliato
echo ""
echo "🧹 Pulizia dati con timestamp futuro..."
docker-compose exec timescaledb psql -U iot_user -d industrial_iot -c "
-- Mostra quanti record hanno timestamp futuro
SELECT 'Records nel futuro:' as info, COUNT(*) as count
FROM sensor_data 
WHERE time > NOW() + INTERVAL '1 hour';

-- Elimina record con timestamp futuro (più di 1 ora avanti)
DELETE FROM sensor_data 
WHERE time > NOW() + INTERVAL '1 hour';

-- Elimina anche record troppo vecchi
DELETE FROM sensor_data 
WHERE time < NOW() - INTERVAL '1 day';

-- Mostra quanti record rimangono
SELECT 'Records rimanenti:' as info, COUNT(*) as count FROM sensor_data;
"

# 4. Inserisci dati di test corretti
echo ""
echo "📊 Inserimento dati di test con UTC corretto..."
docker-compose exec timescaledb psql -U iot_user -d industrial_iot -c "
-- Inserisci dati con timestamp UTC corretti
INSERT INTO sensor_data (time, machine_id, sensor_type, location, value, unit, quality, status) VALUES 
-- Ora corrente UTC
(NOW(), 'MACHINE_001', 'temperature', 'Plant_A_Line_1', 25.5, '°C', 98, 'OK'),
-- 1 minuto fa
(NOW() - INTERVAL '1 minute', 'MACHINE_001', 'temperature', 'Plant_A_Line_1', 26.1, '°C', 97, 'OK'),
-- 2 minuti fa  
(NOW() - INTERVAL '2 minutes', 'MACHINE_001', 'pressure', 'Plant_A_Line_1', 1.23, 'bar', 95, 'OK'),
-- 3 minuti fa
(NOW() - INTERVAL '3 minutes', 'MACHINE_001', 'vibration', 'Plant_A_Line_1', 0.85, 'mm/s', 92, 'OK'),
-- 4 minuti fa
(NOW() - INTERVAL '4 minutes', 'MACHINE_001', 'temperature', 'Plant_A_Line_1', 25.8, '°C', 99, 'OK'),
-- 5 minuti fa
(NOW() - INTERVAL '5 minutes', 'MACHINE_001', 'pressure', 'Plant_A_Line_1', 1.25, 'bar', 94, 'OK');

-- Verifica inserimenti
SELECT 
  sensor_type,
  time,
  EXTRACT(EPOCH FROM (NOW() - time))/60 as minutes_ago,
  value
FROM sensor_data 
ORDER BY time DESC 
LIMIT 6;
"

echo ""
echo "✅ Dati di test inseriti correttamente!"

# 5. Crea script per DAQ con timezone corretto
echo ""
echo "📝 Creando script DAQ con timezone UTC forzato..."
cat > run_daq_utc.sh << 'EOF'
#!/bin/bash

echo "🚀 Avvio DAQ System con timezone UTC forzato"

# Imposta timezone UTC per questo processo
export TZ=UTC

# Ferma eventuali processi DAQ già attivi
pkill -f "python.*main.py" 2>/dev/null
pkill -f "python.*opc_server.py" 2>/dev/null

# Aspetta un momento
sleep 2

echo "🔧 Avvio server OPC UA..."
cd opc_server
TZ=UTC python opc_server.py &
OPC_PID=$!
echo "Server OPC UA avviato (PID: $OPC_PID) con TZ=UTC"

# Attendi che il server sia pronto
sleep 5

echo "📡 Avvio sistema DAQ..."
cd ../daq_system  
TZ=UTC python main.py &
DAQ_PID=$!
echo "Sistema DAQ avviato (PID: $DAQ_PID) con TZ=UTC"

# Salva PID per stop facile
echo $OPC_PID > ../opc_server.pid
echo $DAQ_PID > ../daq_system.pid

cd ..

echo ""
echo "✅ Sistema avviato con timezone UTC!"
echo "📊 I nuovi dati saranno inseriti con timestamp UTC"
echo "🛑 Per fermare: ./stop_system.sh"
EOF

chmod +x run_daq_utc.sh

# 6. Aggiorna script di stop
echo ""
echo "📝 Aggiornando script di stop..."
cat > stop_system.sh << 'EOF'
#!/bin/bash
echo "🛑 Arresto Sistema Industrial IoT"

# Ferma processi Python
if [ -f opc_server.pid ]; then
    OPC_PID=$(cat opc_server.pid)
    echo "Fermando server OPC UA (PID: $OPC_PID)..."
    kill $OPC_PID 2>/dev/null
    rm opc_server.pid
fi

if [ -f daq_system.pid ]; then
    DAQ_PID=$(cat daq_system.pid)
    echo "Fermando sistema DAQ (PID: $DAQ_PID)..."
    kill $DAQ_PID 2>/dev/null
    rm daq_system.pid
fi

# Ferma anche per nome processo (backup)
pkill -f "python.*main.py" 2>/dev/null
pkill -f "python.*opc_server.py" 2>/dev/null

echo "✅ Tutti i processi fermati"
EOF

chmod +x stop_system.sh

echo ""
echo "🎯 Setup Completato!"
echo "=================="
echo ""
echo "📋 Prossimi Passi:"
echo "1. Ferma il sistema DAQ attuale se attivo:"
echo "   ./stop_system.sh"
echo ""
echo "2. Avvia il nuovo sistema con timezone UTC:"
echo "   ./run_daq_utc.sh"
echo ""
echo "3. Verifica in Grafana che i dati appaiano nella timeline corretta"
echo ""
echo "🌐 Grafana: http://localhost:3000"
echo "   - Time range: 'Last 15 minutes'"
echo "   - I dati dovrebbero apparire ora"

# 7. Verifica finale
echo ""
echo "🔍 Verifica finale timestamp..."
docker-compose exec timescaledb psql -U iot_user -d industrial_iot -c "
SELECT 
  'Database time (UTC)' as info,
  NOW()::text as time
UNION ALL
SELECT 
  'Last data age (minutes)' as info,
  ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(time)))/60, 1)::text as time
FROM sensor_data
WHERE time >= NOW() - INTERVAL '1 hour';
"