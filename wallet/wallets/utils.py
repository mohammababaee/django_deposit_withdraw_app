import requests


def request_third_party_deposit():
    response = requests.post("http://172.18.0.1:8010/")
    return response.json()
