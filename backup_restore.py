#!/usr/bin/env python3
"""
This script must solve the challenge https://hackattic.com/challenges/backup_restore 
I assume that the script is going to be used on unix/linus OS.
The challenge implies that we'll send the POST request fast enough, that's why we create docker container before making the GET request to the service to receive the DB dump.

Usage: 
  python3 backup_restore.py <HACKATTIC_TOKEN>
"""

import base64
import requests
import sys
import os
import logging
import docker
import psycopg2
import random
import string
import gzip
import socket
from time import sleep
from subprocess import CalledProcessError, PIPE, check_output

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')


def gen_random_string(k=16):
  return ''.join(random.choices(string.ascii_uppercase + string.digits, k=k))


def run_postgres_container(docker_client, pg_docker_image, container_name, pg_host, pg_port, pg_pass):
  logging.debug("Pulling docker image '{}'".format(pg_docker_image))
  try:
    docker_client.images.pull(pg_docker_image)
  except Exception as e:
    logging.error("Can't pull docker image '{}'".format(pg_docker_image))
    raise e
  logging.info("Pulled docker image '{}'".format(pg_docker_image))

  logging.debug("Running docker container '{}'".format(container_name))
  try:
    docker_client.containers.run(
      pg_docker_image, 
      name=container_name,
      detach=True,
      ports={ '5432/tcp': pg_port },
      environment=[ "POSTGRES_PASSWORD={}".format(pg_pass) ]
    )
  except Exception as e:
    logging.error("Can't run docker container '{}'".format(pg_docker_image))
    raise e
  
  pg_available = False
  attempts = 5
  while not pg_available:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    pg_availability = sock.connect_ex((pg_host, pg_port))
    if pg_availability == 0:
      pg_available = True
      logging.debug("The DBMS in docker container is available")
    attempts-=1
    sleep(1)
    if attempts <= 0:
      logging.error("Can't connect to the DBMS in docker container")
      exit(1)


def get_the_problem(host, problem_path, dump_file):
  logging.info("Get the dump from the challenge")
  res = requests.get(
    "".join([host, problem_path]),
    headers={'Accept': 'application/json'}
    )
  try:
    res.raise_for_status()
  except Exception as e:
    logging.error("Well something is wrong, I can't do the GET request: {}\nReason: {}".format(res.url, e))
    raise e

  dump_file_gz = "{}.gz".format(dump_file)
  logging.debug("Writing database dump archive to '{}'".format(dump_file_gz))
  with open(dump_file_gz, "wb") as f:
    f.write(base64.b64decode(res.json()['dump']))
    logging.info("Postgres database dump archive has been written to '{}'".format(dump_file_gz))

  logging.debug("Unarchiving database dump archive '{}'".format(dump_file_gz))
  with gzip.open(dump_file_gz, 'rb') as archive:
    with open(dump_file, 'wb') as f:
      # I assume that the archive may be huge so let's read it line by line
      for l in archive.readlines():
        f.write(l)
      logging.info("The database dump is unarchived to '{}'".format(dump_file))


# pg_user is equal to pg_database by default, let's keep it that way in this script
def restore_pg_dump(pg_host, pg_port, pg_database, pg_pass):
  logging.info("Restore the database dump to the DBMS instanse running in docker")
  command = "psql -h {} -p {} -d {} -U {} -f {}".format(
    pg_host,
    pg_port,
    pg_database,
    pg_database,
    dump_file
  )
  logging.debug("Execute command: '{}'".format(command))
  try:
    output = check_output(
      command, 
      env=dict(os.environ, PGPASSWORD=pg_pass),
      stderr=PIPE, 
      shell=True
    )
  except CalledProcessError as e:
    logging.error("""Command '{}' failed with exit code {}.
    stdout: {}
    stderr: {}""".format(command, e.returncode, e.output.decode(), e.stderr.decode()))
    raise e
  logging.debug("Dump restoration output:\n{}".format(output.decode('utf-8')))


def get_alive_criminal_ssns(pg_host, pg_port, pg_database, pg_pass):
  logging.info("Get SSN for alive criminals from the dump")
  try:
    con = psycopg2.connect(host=pg_host, port=pg_port, database=pg_database, user=pg_database, password=pg_pass)
    cur = con.cursor()
    cur.execute("SELECT ssn FROM public.criminal_records WHERE status='alive'")
    ssn_list = [value for line in cur.fetchall() for value in line] 
  except psycopg2.DatabaseError as e:
    sys.exit(e)
  finally:
    if con:
      con.close()
  return ssn_list


def send_the_solution(host, solution_path, ssn_list):
  logging.info("Send SSN for alive criminals to the solution endpoint")
  res = requests.post(
    "".join([host, solution_path]), 
    json={"alive_ssns": ssn_list}, 
    headers={'Content-Type': 'application/json'}
    )
  res.raise_for_status()
  logging.info("Response: {}".format(res.text))



if __name__ == "__main__":
  try:
    token = sys.argv[1]
  except IndexError:
    sys.exit(__doc__)
  host = "https://hackattic.com"
  problem_path = "/challenges/backup_restore/problem?access_token={}".format(token)
  solution_path = "/challenges/backup_restore/solve?access_token={}".format(token)
  pg_docker_image = "postgres:14.3-alpine"
  pg_host = "127.0.0.1"
  pg_port = random.randint(35000, 55000)
  pg_database = "postgres"
  pg_pass = gen_random_string()
  container_name = "temp_postgres_{}".format(gen_random_string())
  dump_file = "/tmp/{}".format(gen_random_string())
  docker_client = docker.from_env()
  try:
    run_postgres_container(docker_client, pg_docker_image, container_name, pg_host, pg_port, pg_pass)
    get_the_problem(host, problem_path, dump_file)
    restore_pg_dump(pg_host, pg_port, pg_database, pg_pass)
    send_the_solution(host, solution_path, get_alive_criminal_ssns(pg_host, pg_port, pg_database, pg_pass))
  finally:
    container = docker_client.containers.get(container_name)
    container.stop()
    container.remove()