# tws_worker

IBKR TWS worker that connects to Interactive Brokers TWS / IB Gateway, fetches 1-minute kbar data, and prints results to stdout. Designed to run as a Docker container with a config file mounted as a volume.

## Structure

```
tws_worker/
├── kline_fetcher.py             # main script
├── config.yaml                  # default config (mount your own over /config/config.yaml)
├── pyproject.toml               # uv project with ibapi path dependency
├── Dockerfile                   # multi-stage image using uv
├── ibkr_libs/
│   └── IBJts/source/pythonclient/   # IBKR Python client source (built by uv)
└── examples/
    └── fetch_tws_futures_history_all_contracts.py
```

## Prerequisites

- IBKR TWS or IB Gateway running with API connections enabled
- Python 3.11+ and [uv](https://docs.astral.sh/uv/) (local dev)
- Docker (containerized)

### Enable API in TWS / IB Gateway

`File → Global Configuration → API → Settings`
- Check **Enable ActiveX and Socket Clients**
- Set **Socket port** to match `tws.port` in your config
- Optionally add your host to **Trusted IP Addresses** for remote connections

## Configuration

Copy and edit `config.yaml`. All options:

```yaml
tws:
  host: "127.0.0.1"
  port: 7497        # 7497 = TWS paper | 7496 = TWS live | 4002 = IB Gateway paper | 4001 = IB Gateway live
  client_id: 1      # must be unique per simultaneous connection

contract:
  symbol: "NQ"
  sec_type: "FUT"              # FUT | STK | CASH | OPT | CONTFUT
  exchange: "CME"
  currency: "USD"
  last_trade_date: "202509"    # YYYYMM for futures; leave blank for stocks/forex

fetch:
  interval_seconds: 30         # polling interval (rolling mode)
  bar_size: "1 min"            # 1 sec | 5 secs | 15 secs | 30 secs | 1 min | 5 mins | 1 hour | 1 day
  duration: "300 S"            # look-back window; S=seconds D=days W=weeks
  what_to_show: "TRADES"       # TRADES | MIDPOINT | BID | ASK | BID_ASK
  use_rth: 0                   # 0 = all hours, 1 = regular trading hours only
  request_timeout: 60          # seconds to wait before giving up on a TWS response

  # One-shot mode: set both to fetch a fixed window and exit.
  # Format: "YYYYMMDD HH:mm:ss"  (TWS local time)
  # Leave empty for rolling mode.
  start_time: ""
  end_time: ""

logging:
  level: "INFO"    # DEBUG | INFO | WARNING | ERROR
```

### Operating modes

| Mode | Condition | Behaviour |
|------|-----------|-----------|
| **Rolling** | `start_time` and `end_time` are empty | Fetches last `duration` of bars every `interval_seconds`. Runs until stopped. |
| **One-shot** | Both `start_time` and `end_time` set | Fetches that exact window once, prints bars, then exits. |

## Local development

```bash
cd tws_worker

# Install dependencies (builds ibapi from source via uv path dep)
uv sync

# Run
uv run python kline_fetcher.py

# Override config location
CONFIG_PATH=./my_config.yaml uv run python kline_fetcher.py
```

## Docker

```bash
# Build
docker build -t tws-worker .

# Rolling mode — mount your config
docker run --rm \
  -v /path/to/your/config.yaml:/config/config.yaml \
  tws-worker

# One-shot — override config inline
docker run --rm \
  -e CONFIG_PATH=/config/config.yaml \
  -v /path/to/your/config.yaml:/config/config.yaml \
  tws-worker

# If TWS is on the host machine
docker run --rm \
  --network=host \
  -v /path/to/your/config.yaml:/config/config.yaml \
  tws-worker
```

The image defaults to `/config/config.yaml`. Override with the `CONFIG_PATH` environment variable.

## ibapi dependency

The IBKR Python client (`ibapi`) is not on PyPI; it is built directly from the vendored source at `ibkr_libs/IBJts/source/pythonclient` using a [uv path dependency](https://docs.astral.sh/uv/concepts/dependencies/#path-dependencies). No manual `pip install` or `setup.py` step is needed — `uv sync` handles everything.

To upgrade the API version, unzip the new `twsapi_macunix.*.zip` into `ibkr_libs/`, update the path in `pyproject.toml` if the folder name changed, and run `uv sync` again.
