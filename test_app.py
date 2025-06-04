import requests

BASE_URL = 'http://127.0.0.1:5000'

def test_get_tipos_piso():
    r = requests.get(f'{BASE_URL}/get_tipos_piso')
    assert r.status_code == 200
    print('test_get_tipos_piso passed')

def test_salvar_unidade():
    dados = {
        'localidade': 'Teste',
        'unidade': 'Unidade Teste',
        'medidas_vidros': [{'largura': 1.2, 'comprimento': 2.0, 'area': 2.4}],
        'medidas_sanitarios': [],
        'medidas_internas': [],
        'medidas_externas': []
    }
    r = requests.post(f'{BASE_URL}/salvar_unidade', json=dados)
    assert r.status_code == 200
    print('test_salvar_unidade passed')

if __name__ == '__main__':
    test_get_tipos_piso()
    test_salvar_unidade()
