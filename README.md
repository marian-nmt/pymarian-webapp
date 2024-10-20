# Pymarian Webapp

This is a webserver for pymarian demo

**Features Supported:**
* Test Marian models locally with ease
* Compare multiple models
* Live translation demo (see translation as you speak or type)


## Setup

```bash
git clone https://github.com/marian-nmt/pymarian-webapp
cd pymarian-webapp
pip install -e .

# either one of these should work
pymarian-webapp -h
python -m pymarian_webapp -h
```

## Start the server

```bash
python -m pymarian_webapp  -h
usage: pymarian-webapp [-h] [-d] [-p PORT] [-ho HOST] [-b BASE] [-c CONFIG] [-e]

Deploy Marian model to a RESTful server

options:
  -h, --help            show this help message and exit
  -d, --debug           Run Flask server in debug mode (default: False)
  -p PORT, --port PORT  port to run server on (default: 6060)
  -ho HOST, --host HOST
                        Host address to bind. (default: 0.0.0.0)
  -b BASE, --base BASE  Base prefix path for all the URLs. E.g., /v1 (default: None)
  -c CONFIG, --config CONFIG
                        Config file with MT models (default: None)
  -e, --eager           Eagerly load models (default: False)


```

```bash
python -m pymarian_webapp -d   # -d for debug / hot reload
```

This starts a service on http://localhost:6060 by default.

An example config is `pymarian_webapp/exampless/basic.yml`


## Test multiple translators

```bash
python -m pymarian_webapp -d -c pymarian_webapp/examples/basic.yml
```

## Screenshot

![Pymarian Webapp](docs/pymarian-webapp1.png?raw=true "Pymarian Webapp")