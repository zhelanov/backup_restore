This script must solve the challenge https://hackattic.com/challenges/backup_restore 
I assume that the script is going to be used on unix/linus OS.
The challenge implies that we'll send the POST request fast enough, that's why we create docker container before making the GET request to the service to receive the DB dump.

# Requirements

1. docker daemon is running
2. python3 is present in the system
3. python3 virtualenv is present in the system

# Usage

Prepare the virtual environment, install the deps

```bash
virtualenv -p python3 challenge
. challenge/bin/activate
pip3 install -r requirements.txt
```

Run the script using your hackattic token

```bash
python3 backup_restore.py <HACKATTIC_TOKEN>
```