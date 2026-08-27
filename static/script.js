const socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);

function showTab(tabId, button) {
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active-tab'));
    if (button) button.classList.add('active-tab');
}

function getRadioValue(name) {
    const selected = document.querySelector(`input[name="${name}"]:checked`);
    return selected ? selected.value : null;
}

function saveInspection() {
    const visual = getRadioValue('visual');
    const electrical = getRadioValue('electrical');
    if (!visual || !electrical) {
        alert('Please answer both inspection questions before saving.');
        return;
    }

    fetch('/save_inspection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ visual, electrical })
    }).then(res => res.json()).then(data => {
        if (data.status === 'success') alert('Inspection saved successfully.');
    });
}

function saveChargerResult() {
    const payload = {
        vout: document.getElementById('chargerVout').textContent,
        iout: document.getElementById('chargerIout').textContent,
        temp: document.getElementById('chargerTemp').textContent,
        interface_status: getRadioValue('chargerStatusChoice') || 'error',
        message: document.getElementById('chargerMessage').value || 'No message'
    };

    fetch('/save_charger_result', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(res => res.json()).then(data => {
        if (data.status === 'success') alert('Charger result saved successfully.');
    });
}

function saveBatteryResult() {
    const payload = {
        battery_state: document.getElementById('batteryStateSelect').value || 'not tested',
        charger_connected: getRadioValue('chargerConnected') || 'not tested',
        status: document.getElementById('batteryStatusValue').textContent || 'not tested',
        power_source: document.getElementById('powerSourceValue').textContent || 'not tested',
        power_off_confirmed: getRadioValue('powerOffConfirmed') || 'not tested'
    };

    fetch('/save_battery_result', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(res => res.json()).then(data => {
        if (data.status === 'success') alert('Battery result saved successfully.');
    });
}

function saveDcOutput() {
    const payload = {
        port_1: getRadioValue('port1') || 'not tested',
        port_2: getRadioValue('port2') || 'not tested',
        port_3: getRadioValue('port3') || 'not tested',
        battery_backup: getRadioValue('batteryBackup') || 'not tested',
        notes: document.getElementById('dcNotes').value || ''
    };

    fetch('/save_dc_output', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(res => res.json()).then(data => {
        if (data.status === 'success') alert('DC output result saved successfully.');
    });
}

function updateStatusDisplay(data) {
    document.getElementById('cpuValue').textContent = data.cpu ?? '--';
    document.getElementById('canValue').textContent = data.can_uplink ?? 'DOWN';
    document.getElementById('tempValue').textContent = data.temp ?? '--';
    document.getElementById('humValue').textContent = data.hum ?? '--';
    document.getElementById('eepromValue').textContent = data.eeprom ?? 'ERROR';
    document.getElementById('mqttValue').textContent = data.mqtt ?? 'DOWN';
    document.getElementById('timestampValue').textContent = data.timestamp ?? '--';

    const values = [
        document.getElementById('cpuValue'),
        document.getElementById('canValue'),
        document.getElementById('eepromValue'),
        document.getElementById('mqttValue')
    ];

    values.forEach(el => {
        if (!el) return;
        if (el.textContent === 'ERROR' || el.textContent === 'DOWN' || el.textContent === 'FAIL') {
            el.style.color = '#ef4444';
        } else if (el.textContent === 'GOOD' || el.textContent === 'UP') {
            el.style.color = '#35c46b';
        } else {
            el.style.color = '#edf2ff';
        }
    });
}

function renderQC() {
    fetch('/get_last_log')
        .then(res => res.json())
        .then(log => {
            const list = [];
            const inspection = log['board-inspection-status'] || {};
            const charger = log['charger'] || {};
            const battery = log['battery'] || {};
            const dc = log['dc-output'] || {};

            list.push({ label: 'Visual inspection', ok: inspection.visual === 'yes' });
            list.push({ label: 'Electrical inspection', ok: inspection.electrical === 'yes' });
            list.push({ label: 'Charger interface working', ok: charger.interface_status === 'good' });
            list.push({ label: 'Battery connected', ok: battery.charger_connected === 'connected' || battery.charger_connected === 'disconnected' });
            list.push({ label: 'Battery backup check', ok: dc.battery_backup === 'yes' || dc.battery_backup === 'pass' });
            list.push({ label: 'DC output test', ok: dc.port_1 !== 'not tested' && dc.port_2 !== 'not tested' && dc.port_3 !== 'not tested' });

            const generatedHtml = list.map(item => 
                '<div>' + (item.ok ? '✅' : '❌') + ' ' + item.label + '</div>'
            ).join('');

            document.getElementById('qcResultsList').innerHTML = generatedHtml;
            const qcStatus = list.every(item => item.ok) ? 'PASSED' : 'FAILED';
            document.getElementById('qcResultsList').dataset.qcStatus = qcStatus;
        });
}

function openQCModal() {
    renderQC();
    document.getElementById('qcModal').style.display = 'block';
}

function closeQCModal() {
    document.getElementById('qcModal').style.display = 'none';
}

function confirmQC() {
    const status = document.getElementById('qcResultsList').dataset.qcStatus || 'FAILED';
    const payload = {
        qc_status: status,
        qc_fail_reasons: status === 'FAILED' ? ['One or more QC checks failed'] : [],
        full_log: null,
        timestamp: new Date().toISOString()
    };

    fetch('/write_eeprom_full', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(res => res.json()).then(() => {
        alert('QC written to EEPROM.');
        closeQCModal();
    });
}

function showBoardInfo() {
    fetch('/device_info')
        .then(res => res.json())
        .then(data => {
            const content = document.getElementById('deviceInfoData');
            content.innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
            document.getElementById('deviceInfoModal').style.display = 'block';
        });
}

function closeDeviceInfo() {
    document.getElementById('deviceInfoModal').style.display = 'none';
}

function exportLog() {
    fetch('/export_log')
        .then(res => res.json())
        .then(data => {
            alert(data.message || 'Log exported.');
        });
}

socket.on('status_update', function (data) {
    updateStatusDisplay(data);
    document.getElementById('chargerVout').textContent = data.temp ? data.temp + 'C' : '--';
    document.getElementById('chargerIout').textContent = '0.0A';
    document.getElementById('chargerTemp').textContent = data.temp ? data.temp + 'C' : '--';
    document.getElementById('chargerStatus').textContent = data.mqtt === 'UP' ? 'GOOD' : 'ERROR';
    document.getElementById('batteryStateValue').textContent = 'Charging';
    document.getElementById('chargerConnectedValue').textContent = 'Connected';
    document.getElementById('batteryStatusValue').textContent = 'Running on AC';
    document.getElementById('powerSourceValue').textContent = 'AC/Charger';
});

window.addEventListener('load', () => {
    fetch('/read_status').then(res => res.json()).then(data => updateStatusDisplay(data));
    renderQC();
});
