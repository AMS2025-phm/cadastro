document.getElementById('cadastroForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const dados = { localidade: document.getElementById('localidade').value };
    const response = await fetch('/salvar_unidade', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(dados)
    });
    const result = await response.json();
    alert(result.message);
});