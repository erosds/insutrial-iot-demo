# 🏭 Industrial IoT Demo - TimescaleDB + Grafana

Un sistema completo di acquisizione dati industriali che dimostra l'integrazione tra:
- **Server OPC UA** (simulazione sensori industriali)
- **Sistema DAQ Python** (acquisizione e elaborazione dati)
- **TimescaleDB** (database time-series ottimizzato)
- **Grafana** (dashboard di monitoraggio)

## 🎯 Obiettivi del Progetto

Questo progetto dimostra come costruire un pipeline completo per IoT industriale:

1. **Simulazione Sensori**: Server OPC UA che simula sensori di temperatura, pressione e vibrazione
2. **Acquisizione Dati**: Sistema DAQ che legge dai sensori e valida i dati
3. **Storage Ottimizzato**: TimescaleDB per archiviazione efficiente di serie temporali
4. **Visualizzazione**: Dashboard Grafana per monitoraggio real-time
5. **Rilevamento Anomalie**: Algoritmi per identificare condizioni anomale

## 📁 Struttura del Progetto

```
industrial-iot-demo/
├── docker-compose.yml          # Orchestrazione servizi (TimescaleDB + Grafana)
├── init-db.sql                # Script inizializzazione database
├── config/
│   └── grafana-dashboard.json  # Dashboard Grafana preconfigurata
├── opc_server/
│   ├── __init__.py
│   └── opc_server.py          # Server OPC UA simulato
├── daq_system/
│   ├── __init__.py
│   ├── config.py              # Configurazioni centrali
│   ├── database.py            # Gestione TimescaleDB
│   ├── opc_client.py          # Client OPC UA per DAQ
│   └── main.py                # Sistema DAQ principale
├── requirements.txt           # Dipendenze Python
├── .env.example              # Template variabili ambiente
└── README.md                 # Questo file
```

## 🚀 Avvio Rapido

### 1. Prerequisiti

- **Docker** e **Docker Compose** installati
- **Python 3.8+** installato
- **Git** per clonare il repository

### 2. Setup Ambiente

```bash
# Clona il repository
git clone <repository-url>
cd industrial-iot-demo

# Crea ambiente virtuale Python
python -m venv venv

# Attiva ambiente virtuale
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Installa dipendenze Python
pip install -r requirements.txt

# Copia file configurazione ambiente
cp .env.example .env
# Modifica .env con le tue configurazioni se necessario
```

### 3. Avvio Servizi Infrastruttura

```bash
# Avvia TimescaleDB e Grafana
docker-compose up -d

# Verifica che i servizi siano attivi
docker-compose ps
```

I servizi saranno disponibili su:
- **TimescaleDB**: `localhost:5431`
- **Grafana**: `http://localhost:3000` (admin/admin)

### 4. Avvio Server OPC UA

```bash
# In un terminale separato
cd opc_server
python opc_server.py
```

Il server OPC UA sarà disponibile su `opc.tcp://localhost:4840`

### 5. Avvio Sistema DAQ

```bash
# In un altro terminale
cd daq_system
python main.py
```

Il sistema DAQ inizierà ad acquisire dati ogni 5 secondi e inviarli al database.

## 📊 Accesso Dashboard Grafana

1. Apri browser su `http://localhost:3000`
2. Login: `admin` / `admin`
3. Configura data source TimescaleDB:
   - Type: **PostgreSQL**
   - Host: `timescaledb:5431`
   - Database: `industrial_iot`
   - User: `iot_user`
   - Password: `iot_password`
   - SSL Mode: `disable`
4. Importa dashboard da `config/grafana-dashboard.json`


### Configurazione Sensori

I sensori simulati possono essere configurati in `daq_system/config.py`:

```python
"sensors": {
    "temperature": {
        "min_value": 15.0,
        "max_value": 45.0,
        "base_value": 25.0,
        "noise_factor": 2.0,
        "update_interval": 2.0
    },
    # ... altri sensori
}
```

## 📈 Funzionalità Implementate

### Sistema DAQ
- ✅ **Connessione OPC UA** con riconnessione automatica
- ✅ **Acquisizione batch** dati sensori
- ✅ **Validazione dati** con controllo range e qualità
- ✅ **Elaborazione** con medie mobili e filtri
- ✅ **Rilevamento anomalie** basato su soglie e pattern
- ✅ **Buffer locale** per gestire disconnessioni temporanee
- ✅ **Statistiche operative** dettagliate

### Database TimescaleDB
- ✅ **Hypertables** per partizionamento automatico
- ✅ **Compressione automatica** per ottimizzare storage
- ✅ **Retention policies** per gestione automatica dati
- ✅ **Viste materializzate** per query aggregate veloci
- ✅ **Indicizzazione ottimizzata** per query time-series

### Server OPC UA
- ✅ **Simulazione realistica** sensori industriali
- ✅ **Valori dinamici** con trend e rumore
- ✅ **Metadati completi** (qualità, timestamp, stato)
- ✅ **Namespace strutturato** per organizzazione dati

### Dashboard Grafana
- ✅ **Monitoraggio real-time** valori sensori
- ✅ **Trend analysis** con grafici temporali
- ✅ **Alerting** per condizioni anomale
- ✅ **Statistiche sistema** e health monitoring
- ✅ **Vista storica** con aggregazioni

## 🔍 Monitoraggio e Debug

### Log del Sistema

I log sono disponibili in:
- **DAQ System**: `logs/industrial_iot.log`
- **Docker logs**: `docker-compose logs -f timescaledb`

### Architettura del Sistema

```
[Sensori Fisici] → [Server OPC UA] → [DAQ Client] → [TimescaleDB] → [Grafana]
                                        ↓
                                   [Anomaly Detection]
                                        ↓
                                   [Alerting System]
```

### Pattern Implementati

- **Singleton Pattern**: Per configurazioni e database manager
- **Observer Pattern**: Per monitoraggio eventi anomalie
- **Connection Pooling**: Per performance database
- **Circuit Breaker**: Per resilienza connessioni
- **Batch Processing**: Per ottimizzazione throughput