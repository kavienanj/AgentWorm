FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip curl nmap net-tools iproute2 \
    openssh-client openssh-server sshpass gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /dba
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY agent.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
