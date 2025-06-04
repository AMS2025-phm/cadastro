document.addEventListener('DOMContentLoaded', function () {
    const estacionamentoCheckbox = document.getElementById('estacionamento');
    const estacionamentoCobertoGroup = document.getElementById('estacionamento-coberto-group');

    function updateEstacionamentoCobertoVisibility() {
        estacionamentoCobertoGroup.classList.toggle('hidden', !estacionamentoCheckbox.checked);
        if (!estacionamentoCheckbox.checked) {
            document.getElementById('estacionamento_coberto').checked = false;
        }
    }

    estacionamentoCheckbox.addEventListener('change', updateEstacionamentoCobertoVisibility);
    updateEstacionamentoCobertoVisibility();

    async function loadDropdownOptions() {
        try {
            const pisoRes = await fetch('/get_tipos_piso');
            const paredeRes = await fetch('/get_tipos_parede');

            const tiposPiso = await pisoRes.json();
            const tiposParede = await paredeRes.json();

            const tiposPisoContainer = document.getElementById('tipos-piso-checkboxes');
            const tiposParedeContainer = document.getElementById('tipos-parede-checkboxes');

            tiposPisoContainer.innerHTML = '';
            tiposPiso.forEach((piso, index) => {
                const id = `piso_${index}`;
                tiposPisoContainer.innerHTML += `<input type="checkbox" id="${id}" name="tipos_piso_selecionados" value="${piso}">
                <label for="${id}">${piso}</label>`;
            });

            tiposParedeContainer.innerHTML = '';
            tiposParede.forEach((parede, index) => {
                const id = `parede_${index}`;
                tiposParedeContainer.innerHTML += `<input type="checkbox" id="${id}" name="tipos_parede_selecionados" value="${parede}">
                <label for="${id}">${parede}</label>`;
            });
        } catch (error) {
            console.error('Erro ao carregar opções:', error);
        }
    }

    loadDropdownOptions();

    function addMedidaBlock(container, type) {
        const index = container.children.length;
        const block = document.createElement('div');
        block.style.display = 'flex';
        block.style.gap = '10px';
        block.style.margin = '5px 0';

        block.innerHTML = `
            <label>${type} #${index + 1}</label>
            <input type="number" placeholder="Largura" class="largura" step="0.01">
            <input type="number" placeholder="Comprimento" class="comprimento" step="0.01">
            <input type="number" placeholder="Área" class="area" step="0.01" readonly>
        `;

        const largura = block.querySelector('.largura');
        const comprimento = block.querySelector('.comprimento');
        const area = block.querySelector('.area');

        function calcularArea() {
            const l = parseFloat(largura.value) || 0;
            const c = parseFloat(comprimento.value) || 0;
            area.value = (l * c).toFixed(2);
        }

        largura.addEventListener('input', calcularArea);
        comprimento.addEventListener('input', calcularArea);

        container.appendChild(block);
    }

    document.getElementById('addVidroBtn').addEventListener('click', () => addMedidaBlock(document.getElementById('vidros-container'), 'Vidro'));
    document.getElementById('addSanitarioBtn').addEventListener('click', () => addMedidaBlock(document.getElementById('sanitarios-container'), 'Sanitário'));
    document.getElementById('addInternaBtn').addEventListener('click', () => addMedidaBlock(document.getElementById('internas-container'), 'Área Interna'));
    document.getElementById('addExternaBtn').addEventListener('click', () => addMedidaBlock(document.getElementById('externas-container'), 'Área Externa'));

    document.getElementById('cadastroForm').addEventListener('submit', async function (e) {
        e.preventDefault();

        const formData = new FormData(this);
        const dados = {};

        formData.forEach((value, key) => {
            if (dados[key]) {
                if (!Array.isArray(dados[key])) {
                    dados[key] = [dados[key]];
                }
                dados[key].push(value);
            } else {
                dados[key] = value;
            }
        });

        function coletarMedidas(containerId) {
            const container = document.getElementById(containerId);
            const medidas = [];
            container.querySelectorAll('div').forEach(div => {
                const largura = parseFloat(div.querySelector('.largura')?.value) || 0;
                const comprimento = parseFloat(div.querySelector('.comprimento')?.value) || 0;
                const area = parseFloat(div.querySelector('.area')?.value) || 0;
                medidas.push({ largura, comprimento, area });
            });
            return medidas;
        }

        dados.medidas_vidros = coletarMedidas('vidros-container');
        dados.medidas_sanitarios = coletarMedidas('sanitarios-container');
        dados.medidas_internas = coletarMedidas('internas-container');
        dados.medidas_externas = coletarMedidas('externas-container');

        try {
            const response = await fetch('/salvar_unidade', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(dados)
            });
            const result = await response.json();
            alert(result.message);
        } catch (err) {
            console.error('Erro ao enviar:', err);
            alert('Erro ao enviar os dados.');
        }
    });
});
