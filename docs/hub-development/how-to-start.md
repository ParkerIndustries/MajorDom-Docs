## Usage

Flash ready image from releases page to a SD card (or MMC/eMMC/SSD).

## Develop Locally

### Setup

Clone the repo and cd to it

Install dependencies
```sh
pip install poetry 
poetry install
```

Generate token signing keys
```sh
ssh-keygen -t rsa -b 4096 -m PEM -f cloud.key -N ""
openssl rsa -in cloud.key -pubout -outform PEM -out cloud.key.pub
ssh-keygen -t rsa -b 4096 -m PEM -f hub.key -N ""
openssl rsa -in hub.key -pubout -outform PEM -out hub.key.pub
```

Prepare .env
```sh
cp example.env .env
```

Read CLI options
```sh
poetry run python3 majordom_hub --help
```

Run
```sh
poetry run python3 majordom_hub --virtual 
```
