import requests
import json

url = "https://pub.orcid.org/v3.0/expanded-search/"

query = (
    'current-institution-affiliation-name:'
    '"Centro de Investigacion en Tecnologias de Informacion y Sistemas"'
)

params = {
    "q": query,
    "rows": 10  #limit output
}

headers = {
    "Accept": "application/json",
    "User-Agent": "orcid-test-script"
}

response = requests.get(url, params=params, headers=headers)
response.raise_for_status()

data = response.json()

# Pretty print JSON
print(json.dumps(data, indent=2, ensure_ascii=False))

print("number of results: ", response.json().get("num-found", 0))

# Print orcids
orcids = []

results = data.get("expanded-result", [])

for r in results:
    orcids.append(r.get("orcid-id"))

print(f"len of orcids[]:", len(orcids))
for id in orcids:
    print(id)
