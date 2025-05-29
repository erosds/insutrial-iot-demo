#!/usr/bin/env python3
# test_anomalies_fixed.py - Script per generare anomalie compatibili con schema DB

import sys
import os
from datetime import datetime, timezone
import random
import time

# Aggiunge il path del progetto per gli import  
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from daq_system.config import settings
from daq_system.database import sensor_db
from loguru import logger

def create_test_anomalies_fixed():
    """
    Crea anomalie di test nel database COMPATIBILI con il schema esistente.
    Usa solo valori di status permessi: 'OK', 'WARNING', 'ERROR'.
    """
    logger.info("🧪 Creazione anomalie di test (schema compatibile)...")
    
    # Mappa tipi anomalia a status validi e descrizioni
    anomaly_types = [
        ('OUT_OF_RANGE', 'ERROR', 'Temperatura fuori range di sicurezza', 4.0),
        ('HIGH_VIBRATION', 'ERROR', 'Vibrazione eccessiva rilevata', 4.2),
        ('LOW_QUALITY', 'WARNING', 'Qualità segnale degradata', 2.5),
        ('RAPID_CHANGE', 'WARNING', 'Cambiamento rapido nei valori', 3.1),
        ('EXTENDED_RANGE', 'WARNING', 'Valore in range di attenzione', 2.0),
        ('SENSOR_FAULT', 'ERROR', 'Malfunzionamento sensore rilevato', 4.5),
        ('THRESHOLD_EXCEEDED', 'WARNING', 'Soglia operativa superata', 2.8),
        ('COMM_ERROR', 'ERROR', 'Errore comunicazione sensore', 3.8)
    ]
    
    anomalies_created = 0
    
    for i, (anomaly_type, status, description, severity_value) in enumerate(anomaly_types):
        try:
            # Crea timestamp distribuiti negli ultimi 60 minuti
            minutes_ago = random.randint(1, 60)
            
            # Fix: usa replace per evitare errori sui minuti
            base_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
            timestamp = base_time - timezone.timedelta(minutes=minutes_ago)
            
            # Record anomalia COMPATIBILE con schema DB
            anomaly_record = {
                'timestamp': timestamp,
                'machine_id': settings.daq.machine_id,
                'sensor_type': 'anomaly',  # Tipo speciale per anomalie
                'location': settings.daq.location,
                'value': severity_value,   # Valore numerico severità
                'unit': 'level',          # Unità generica
                'quality': 100,           # Qualità sempre 100 per anomalie
                'status': status          # SOLO valori permessi: OK, WARNING, ERROR
            }
            
            # Inserisce nel database
            success = sensor_db.insert_sensor_reading(**anomaly_record)
            
            if success:
                anomalies_created += 1
                logger.success(f"✅ Anomalia {anomaly_type} creata (status: {status}, severity: {severity_value})")
            else:
                logger.error(f"❌ Errore creazione anomalia {anomaly_type}")
                
        except Exception as e:
            logger.error(f"Errore creazione anomalia {anomaly_type}: {e}")
    
    logger.info(f"🎯 Anomalie di test create: {anomalies_created}/{len(anomaly_types)}")
    return anomalies_created

def create_sensor_anomalies():
    """
    Crea anomalie integrate nei dati dei sensori normali.
    Questo approccio è più realistico e compatibile con lo schema.
    """
    logger.info("📊 Creazione dati sensori con anomalie integrate...")
    
    current_time = datetime.now(timezone.utc)
    readings_created = 0
    anomalies_created = 0
    
    # Crea 30 letture negli ultimi 30 minuti con alcune anomalie
    for i in range(30):
        try:
            # Timestamp distribuito negli ultimi 30 minuti
            minutes_ago = i
            timestamp = current_time - timezone.timedelta(minutes=minutes_ago)
            timestamp = timestamp.replace(second=0, microsecond=0)
            
            # Valori base realistici
            temp_base = 25.0 + random.uniform(-3, 3)
            press_base = 1.2 + random.uniform(-0.1, 0.1)  
            vib_base = 0.8 + random.uniform(-0.2, 0.2)
            
            # Genera occasionalmente valori anomali (30% probabilità)
            temp_status = 'OK'
            press_status = 'OK'
            vib_status = 'OK'
            temp_quality = random.randint(90, 100)
            press_quality = random.randint(90, 100)
            vib_quality = random.randint(90, 100)
            
            if random.random() < 0.3:  # 30% probabilità di anomalia
                anomaly_type = random.choice(['temp_high', 'temp_low', 'press_high', 'press_low', 'vib_high', 'quality_low'])
                
                if anomaly_type == 'temp_high':
                    temp_base = random.uniform(42, 50)  # Temperatura alta
                    temp_status = 'ERROR' if temp_base > 45 else 'WARNING'
                elif anomaly_type == 'temp_low':
                    temp_base = random.uniform(10, 18)  # Temperatura bassa
                    temp_status = 'WARNING'
                elif anomaly_type == 'press_high':
                    press_base = random.uniform(2.1, 2.8)  # Pressione alta
                    press_status = 'ERROR' if press_base > 2.5 else 'WARNING'
                elif anomaly_type == 'press_low':
                    press_base = random.uniform(0.5, 0.8)  # Pressione bassa
                    press_status = 'WARNING'
                elif anomaly_type == 'vib_high':
                    vib_base = random.uniform(2.6, 3.5)  # Vibrazione alta
                    vib_status = 'ERROR' if vib_base > 3.0 else 'WARNING'
                elif anomaly_type == 'quality_low':
                    # Qualità bassa su sensore casuale
                    low_quality = random.randint(60, 79)
                    if random.choice([True, False]):
                        temp_quality = low_quality
                        temp_status = 'WARNING'
                    else:
                        press_quality = low_quality
                        press_status = 'WARNING'
            
            # Crea i record sensori
            sensors_data = [
                {
                    'timestamp': timestamp,
                    'machine_id': settings.daq.machine_id,
                    'sensor_type': 'temperature',
                    'location': settings.daq.location,
                    'value': round(temp_base, 2),
                    'unit': '°C',
                    'quality': temp_quality,
                    'status': temp_status
                },
                {
                    'timestamp': timestamp,
                    'machine_id': settings.daq.machine_id,
                    'sensor_type': 'pressure',
                    'location': settings.daq.location,
                    'value': round(press_base, 2),
                    'unit': 'bar',
                    'quality': press_quality,
                    'status': press_status
                },
                {
                    'timestamp': timestamp,
                    'machine_id': settings.daq.machine_id,
                    'sensor_type': 'vibration',
                    'location': settings.daq.location,
                    'value': round(vib_base, 2),
                    'unit': 'mm/s',
                    'quality': vib_quality,
                    'status': vib_status
                }
            ]
            
            # Inserisce nel database
            inserted = sensor_db.insert_batch_readings(sensors_data)
            readings_created += inserted
            
            # Conta anomalie (status != 'OK')
            anomalies_in_batch = sum(1 for data in sensors_data if data['status'] != 'OK')
            anomalies_created += anomalies_in_batch
            
        except Exception as e:
            logger.error(f"Errore creazione dati: {e}")
    
    logger.success(f"✅ Creati {readings_created} punti dati con {anomalies_created} anomalie integrate")
    return readings_created, anomalies_created

def verify_anomalies_in_db():
    """
    Verifica le anomalie nel database con query multiple.
    """
    logger.info("🔍 Verifica anomalie nel database...")
    
    try:
        # Metodo 1: Cerca record con sensor_type = 'anomaly'
        direct_anomalies = sensor_db.get_latest_readings(
            machine_id=settings.daq.machine_id,
            sensor_type='anomaly',
            limit=20
        )
        
        logger.info(f"📊 Anomalie dirette (sensor_type='anomaly'): {len(direct_anomalies)}")
        for anomaly in direct_anomalies[:5]:  # Mostra solo prime 5
            logger.info(f"   - Status: {anomaly['status']}, Value: {anomaly['value']}, Time: {anomaly['time']}")
        
        # Metodo 2: Cerca sensori con status != 'OK'
        with sensor_db.db_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT sensor_type, status, COUNT(*) as count
                    FROM sensor_data 
                    WHERE machine_id = %s 
                      AND time >= NOW() - INTERVAL '2 hours'
                      AND status != 'OK'
                    GROUP BY sensor_type, status
                    ORDER BY count DESC
                """, (settings.daq.machine_id,))
                
                sensor_anomalies = cursor.fetchall()
                
        logger.info(f"📊 Anomalie nei sensori (status != 'OK'): {len(sensor_anomalies)} tipi")
        for sensor_type, status, count in sensor_anomalies:
            logger.info(f"   - {sensor_type}: {count} con status '{status}'")
        
        # Metodo 3: Totale anomalie per Grafana
        with sensor_db.db_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                # Query esatta che usa Grafana
                cursor.execute("""
                    SELECT COALESCE(COUNT(*), 0) as anomaly_count
                    FROM sensor_data 
                    WHERE sensor_type = 'anomaly' 
                      AND machine_id = %s
                      AND time >= NOW() - INTERVAL '1 hour'
                """, (settings.daq.machine_id,))
                
                grafana_count = cursor.fetchone()[0]
                
        logger.info(f"📊 Conteggio per Grafana (ultima ora): {grafana_count}")
        
        return len(direct_anomalies) + len(sensor_anomalies)
        
    except Exception as e:
        logger.error(f"Errore verifica anomalie: {e}")
        return 0

def clean_old_data():
    """
    Pulisce dati vecchi per fare spazio ai nuovi test.
    """
    logger.info("🧹 Pulizia dati vecchi...")
    
    try:
        with sensor_db.db_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                # Elimina dati più vecchi di 2 ore
                cursor.execute("""
                    DELETE FROM sensor_data 
                    WHERE time < NOW() - INTERVAL '2 hours'
                """)
                
                deleted_count = cursor.rowcount
                conn.commit()
                
        logger.info(f"🗑️ Eliminati {deleted_count} record vecchi")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Errore pulizia dati: {e}")
        return 0

def main():
    """
    Funzione principale per test anomalie FIXED.
    """
    print("🧪 Test Sistema Anomalie Industrial IoT (FIXED)")
    print("==============================================")
    
    # Test connessione database
    print("🔧 Test connessione database...")
    if not sensor_db.db_manager.test_connection():
        print("❌ Connessione database fallita!")
        return
    print("✅ Database connesso")
    
    # Menu opzioni
    print("\nOpzioni disponibili:")
    print("1. Crea anomalie dirette (sensor_type='anomaly')")
    print("2. Crea dati sensori con anomalie integrate")
    print("3. Verifica anomalie esistenti")
    print("4. Pulisci dati vecchi")
    print("5. Tutto (4+1+2+3)")
    
    choice = input("\nScegli opzione (1-5): ").strip()
    
    if choice in ['4', '5']:
        print("\n" + "="*50)
        cleaned = clean_old_data()
        print(f"Record puliti: {cleaned}")
    
    if choice in ['1', '5']:
        print("\n" + "="*50)
        created = create_test_anomalies_fixed()
        print(f"Anomalie dirette create: {created}")
    
    if choice in ['2', '5']:
        print("\n" + "="*50)
        readings, anomalies = create_sensor_anomalies()
        print(f"Dati sensori creati: {readings} letture, {anomalies} anomalie")
    
    if choice in ['3', '5']:
        print("\n" + "="*50)
        found = verify_anomalies_in_db()
        print(f"Anomalie totali trovate: {found}")
    
    print("\n🎯 Test completato!")
    print("💡 Ora controlla Grafana su http://localhost:3000")
    print("   Il conteggio anomalie dovrebbe essere > 0")
    print("   Controlla anche la tabella 'Stato Corrente Sensori' per status WARNING/ERROR")

if __name__ == "__main__":
    # Configura logging
    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        colorize=True
    )
    
    main()