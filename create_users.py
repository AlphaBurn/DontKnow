import requests

for i in range(13, 60):

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:159.0) Gecko/20100101 Firefox/159.0',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        # 'Accept-Encoding': 'gzip, deflate',
        'Referer': 'http://10.201.73.104:5000/',
        'Connection': 'keep-alive',
        # 'Cookie': 'session=eyJ1c2VybmFtZSI6InRlc3QxMiJ9.avLicA.9bIx2sijgjmMp-Qp5Kaj7smXK_o',
        'Priority': 'u=4',
        'Content-Type': 'application/json',
        'Origin': 'http://10.201.73.104:5000',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
    }

    json_data = {
        'username': f"stress_{i}",
    }

    response = requests.post('http://192.168.1.2:5000/set_username', headers=headers, json=json_data)
