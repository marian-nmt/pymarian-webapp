# Pymarian Webapp

This is a webserver for pymarian demo

**Features Supported:**
* Test Marian models locally with ease
* Compare multiple models
* Live translation demo (see translation as you speak or type)


## Setup/installation

pymarian-webapp requires Python 3.9 or later.

```bash
git clone https://github.com/marian-nmt/pymarian-webapp
cd pymarian-webapp

# optionally create an env
python3 -m venv venv
. venv/bin/activate

# install
pip install .
```

## Start the server

You need to provide the model with a config file which tells it where to find models. Two models types are supported: a path to a local Marian model, or the [Microsoft Translator API](https://learn.microsoft.com/en-us/azure/ai-services/translator/reference/v3-0-reference), which requires an API subscription key.

```bash
pymarian-webapp -c pymarian_webapp/examples/basic.yml
```
This starts a service on http://localhost:6060 by default. See the config file for other model options.

More options are available and can be see via the `-h` flag:

```bash
usage: pymarian-webapp [-h] [-d] [-p PORT] [-ho HOST] [-b BASE] [-c CONFIG] [-e] [-me [METRICS ...]]

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
  -me [METRICS ...], --metrics [METRICS ...]
                        List of MT evaluation metrics. Only QE metrics are supported. (default: ['wmt20-comet-qe-da',
                        'wmt22-cometkiwi-da', 'wmt23-cometkiwi-da-xl'])
```

## Test multiple translators

```bash
python -m pymarian_webapp -d -c pymarian_webapp/examples/basic.yml
```

## Screenshot

![Pymarian Webapp](docs/pymarian-webapp1.png?raw=true "Pymarian Webapp")