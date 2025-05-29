#!/bin/bash

echo "🕐 Diagnosi Problema Timezone"
echo "============================"

# 1. Timezone del sistema host
echo "🖥️  Sistema Host:"
echo "   Timezone: $(timedatectl show --property=Timezone --value)"
echo "   Ora locale: $(date)"
echo "   Ora UTC: $(date -u)"

# 2. Timezone container TimescaleDB
echo -e "\n🗄️  Container TimescaleDB:"
echo "   Timezone container:"
docker-compose exec timescaledb date
echo "   Timezone impostato in PostgreSQL:"
docker-compose exec timescaledb psql -U iot_user -d industrial_iot -c "SHOW timezone;"
echo "   Ora corrente in DB:"
docker-compose exec timescaledb psql -U iot_user -d industrial_iot -c "SELECT NOW() as db_time, NOW() AT TIME ZONE 'UTC' as utc_time;"

# 3. Ultimi dati nel database
echo -e "\n📊 Ultimi Dati nel Database:"
docker-compose exec timescaledb psql -U iot_user -d industrial_iot -c "
SELECT 
    sensor_type,
    time as timestamp_stored,
    time AT TIME ZONE 'UTC' as timestamp_utc,
    NOW() - time as time_ago,
    value
FROM sensor_data 
ORDER BY time DESC 
LIMIT 5;
"

# 4. Range di dati disponibili
echo -e "\n📈 Range Dati Disponibili:"
docker-compose exec timescaledb psql -U iot_user -d industrial_iot -c "
SELECT 
    MIN(time) as first_record,
    MAX(time) as last_record,
    NOW() as current_time,
    NOW() - MAX(time) as minutes_since_last
FROM sensor_data;
"

# 5. Timezone browser (approssimativo)
echo -e "\n🌐 Info Sistema:"
echo "   Fuso orario rilevato: $(timedatectl show --property=Timezone --value)"
echo "   Offset UTC: $(date +%z)"

echo -e "\n💡 Analisi:"
echo "   Se 'minutes_since_last' > 1-2 minuti, c'è un problema di timezone"
echo "   Se i timestamp sono nel futuro, il timezone è sbagliato"