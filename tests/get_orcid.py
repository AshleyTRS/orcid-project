import requests
import json

URL = "https://pub.orcid.org/v3.0/0000-0003-2043-8766/works/161465810"

headers = {
    "Accept": "application/json",
    "User-Agent": "orcid-harvester/test-script"
}

def main():
    response = requests.get(URL, headers=headers)
    response.raise_for_status()

    data = response.json()
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
