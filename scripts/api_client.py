"""
Simple API client for sign up and sign in against the local Django API.

Usage:
  python scripts/api_client.py signup --email user@example.com --name "User" --password secret
  python scripts/api_client.py login --email user@example.com --password secret

It reads BASE_URL from environment or defaults to http://localhost:8000/api/.
Prints JSON responses to stdout.
"""
import os
import sys
import argparse
import requests
import json

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api/")


def signup(email, name, password):
    url = BASE_URL.rstrip("/") + "/auth/signup/"
    payload = {
        "name": name,
        "email": email,
        "password": password,
        "confirm_password": password,
    }
    resp = requests.post(url, json=payload, timeout=10)
    try:
        print(json.dumps(resp.json(), indent=2))
    except Exception:
        print(resp.text)
    return resp


def login(email, password):
    url = BASE_URL.rstrip("/") + "/auth/login/"
    payload = {"email": email, "password": password}
    resp = requests.post(url, json=payload, timeout=10)
    try:
        print(json.dumps(resp.json(), indent=2))
    except Exception:
        print(resp.text)
    return resp


def main(argv):
    parser = argparse.ArgumentParser(prog="api_client")
    sub = parser.add_subparsers(dest="cmd")

    p_signup = sub.add_parser("signup")
    p_signup.add_argument("--email", required=True)
    p_signup.add_argument("--name", required=True)
    p_signup.add_argument("--password", required=True)

    p_login = sub.add_parser("login")
    p_login.add_argument("--email", required=True)
    p_login.add_argument("--password", required=True)

    args = parser.parse_args(argv)
    if args.cmd == "signup":
        return signup(args.email, args.name, args.password)
    if args.cmd == "login":
        return login(args.email, args.password)

    parser.print_help()
    return None


if __name__ == "__main__":
    main(sys.argv[1:])
