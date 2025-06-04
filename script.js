document.getElementById('cadastroForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const dados = {
        localidade: document.getElementById('localidade').value,
        unidade: document.getElementById('unidade').value
    };
    const response = await fetch('/salvar_unidade', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(dados)
    });
    const result = await response.json();
    document.getElementById('message-box').textContent = result.message;
});

async function loadDropdownOptions() {
    try {
        const res = await fetch('/get_tipos_piso');
        const tipos = await res.json();
        console.log('Tipos de piso:', tipos);
    } catch (err) {
        console.error('Erro ao carregar tipos:', err);
    }
}
loadDropdownOptions();
