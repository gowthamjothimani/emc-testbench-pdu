var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);

// ========== TAB SWITCHING ==========
function showTab(tabId, btnElement) {
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    const targetTab = document.getElementById(tabId);
    if (targetTab) targetTab.classList.add('active');

    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active-tab'));
    if (btnElement) btnElement.classList.add('active-tab');
}

// ========== LIVE UTC CLOCK ==========
function tickClock() {
    const el = document.getElementById('stat_time');
    if (el) el.textContent = new Date().toISOString().substr(11, 8) + 'Z';
}
setInterval(tickClock, 1000);
tickClock();

// ========== STATUS BAR ==========
function setStatusBox(el, ok, label) {
    el.classList.remove('good', 'error');
    el.classList.add(ok ? 'good' : 'error');
    el.textContent = label;
}

socket.on('status_bar_update', function (data) {
    document.getElementById('stat_cpu').textContent = (data.cpu ?? '--') + '%';

    const temp = data.temperature;
    const hum = data.humidity;
    document.getElementById('stat_temp').textContent = (temp !== null && temp !== undefined ? temp : '--') + ' \u00b0C';
    document.getElementById('stat_hum').textContent = (hum !== null && hum !== undefined ? hum : '--') + ' %';

    const can = data.can || {};
    const canEl = document.getElementById('stat_can');
    const canOk = can.state === 'UP' && can.health === 'OK';
    setStatusBox(canEl, canOk, `${can.state || '--'} / ${can.health || '--'}`);
    canEl.title = can.detail || '';

    const eepromEl = document.getElementById('stat_eeprom');
    const eepromOk = !!(data.eeprom && data.eeprom.present);
    setStatusBox(eepromEl, eepromOk, eepromOk ? 'GOOD' : 'ERROR');

    const mqttEl = document.getElementById('stat_mqtt');
    const mqtt = data.mqtt || {};
    const mqttOk = !!mqtt.connected || !!mqtt.reachable;
    setStatusBox(mqttEl, mqttOk, mqtt.connected ? 'CONNECTED' : (mqtt.reachable ? 'REACHABLE' : 'DOWN'));
});

socket.on('mqtt_status', function (data) {
    const mqttEl = document.getElementById('stat_mqtt');
    if (!mqttEl) return;
    setStatusBox(mqttEl, !!data.connected, data.connected ? 'CONNECTED' : 'DOWN');
});

// ========== MQTT CONFIG MODAL ==========
function openMQTTConfig() {
    fetch('/get_mqtt_config')
        .then(r => r.json())
        .then(config => {
            document.getElementById('mqtt_hostname').value = config.hostname || '';
            document.getElementById('mqtt_port').value = config.port || '';
            document.getElementById('mqtt_topic').value = config.topic || '';
            document.getElementById('mqtt_username').value = config.username || '';
            document.getElementById('mqtt_password').value = config.password || '';
        })
        .catch(err => console.error('Failed to load MQTT config:', err));
    document.getElementById('mqttConfigModal').style.display = 'block';
}

function closeMQTTConfig() {
    document.getElementById('mqttConfigModal').style.display = 'none';
}

function saveMQTTConfig() {
    const config = {
        hostname: document.getElementById('mqtt_hostname').value,
        port: parseInt(document.getElementById('mqtt_port').value),
        topic: document.getElementById('mqtt_topic').value,
        username: document.getElementById('mqtt_username').value,
        password: document.getElementById('mqtt_password').value
    };
    fetch('/update_mqtt', { method: 'POST', body: JSON.stringify(config), headers: { 'Content-Type': 'application/json' } })
        .then(r => r.json())
        .then(data => console.log(data));
    closeMQTTConfig();
}

function exportLog() {
    socket.emit('export_log');
    alert('Log export sent to MQTT broker.');
}

// ========== INSPECTION TAB ==========
function saveInspection() {
    const visual = document.querySelector('input[name="visual"]:checked');
    const electrical = document.querySelector('input[name="electrical"]:checked');

    if (!visual || !electrical) {
        alert('Please answer both inspection questions before saving.');
        return;
    }

    fetch('/save_inspection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ visual: visual.value, electrical: electrical.value })
    })
    .then(r => r.json())
    .then(data => {
        const msg = document.getElementById('inspectionSavedMsg');
        if (data.status === 'success') {
            msg.textContent = '\u2705 Inspection saved.';
        } else {
            msg.textContent = '\u274c ' + (data.message || 'Error saving inspection.');
        }
    })
    .catch(err => alert('Error: ' + err.message));
}

// ========== CHARGER TAB ==========
// Real driver field names live under data.pdu_chgr (chgr_vout_DC / chgr_iout / chgr_temp / chgr_error).
// chgr_error non-empty (or pdu_chgr missing) means no real CAN frames -> show NA, never a fabricated number.
function renderCharger(payload) {
    const chgr = (payload.data || {}).pdu_chgr || {};
    const hasFault = !payload.working;

    document.getElementById('charger_vout').textContent = hasFault ? 'NA' : (chgr.chgr_vout_DC ?? 'NA');
    document.getElementById('charger_iout').textContent = hasFault ? 'NA' : (chgr.chgr_iout ?? 'NA');
    document.getElementById('charger_temp').textContent = hasFault ? 'NA' : (chgr.chgr_temp ?? 'NA');

    const stateEl = document.getElementById('charger_state');
    if (payload.working) {
        setStatusBox(stateEl, true, 'GOOD');
    } else {
        stateEl.classList.remove('good', 'error');
        stateEl.classList.add('na');
        stateEl.textContent = 'NA';
    }
    document.getElementById('charger_message').textContent = payload.message || '--';
}

socket.on('charger_data', renderCharger);

function testCharger() {
    document.getElementById('charger_message').textContent = 'Reading...';
    fetch('/charger/read')
        .then(r => r.json())
        .then(renderCharger)
        .catch(err => {
            document.getElementById('charger_message').textContent = 'Fetch error: ' + err.message;
        });
}

// ========== BATTERY TAB ==========
// Real driver field names live under data.pdu_batt.batt_basic / batt_advance
// (batt_voltage, batt_current, batt_soc, batt_state, batt_charger are all
// STRINGS already formatted by the driver, e.g. "52.10V", "connected").
//
// "lockedWorking" (from log_exporter's session latch) is what decides the
// GOOD/NA badge - NOT the instantaneous `working` flag. That's the fix for
// the false "error" this used to show the moment the charger disconnects
// for the backup test: once the battery interface has proven itself once
// this session, the badge stays GOOD even while batt_charger flips to
// "disconnected". The live batt_charger value itself is still shown as
// plain telemetry either way.
function renderBattery(payload) {
    const batt = (payload.data || {}).pdu_batt || {};
    const basic = batt.batt_basic || {};
    const adv = batt.batt_advance || {};
    const noFrames = !basic || Object.keys(basic).length === 0;

    document.getElementById('batt_voltage').textContent = noFrames ? 'NA' : (basic.batt_voltage ?? 'NA');
    document.getElementById('batt_current').textContent = noFrames ? 'NA' : (basic.batt_current ?? 'NA');
    document.getElementById('batt_soc').textContent = noFrames ? 'NA' : (basic.batt_soc ?? 'NA');
    document.getElementById('batt_state').textContent = noFrames ? 'NA' : (basic.batt_state ?? 'NA');
    document.getElementById('batt_charger_conn').textContent = noFrames ? 'NA' : (basic.batt_charger ?? 'NA');

    document.getElementById('batt_temp_max').textContent = noFrames ? 'NA' : (basic.batt_temp_max ?? 'NA');
    document.getElementById('batt_temp_min').textContent = noFrames ? 'NA' : (basic.batt_temp_min ?? 'NA');
    const health = adv.batt_health || {};
    document.getElementById('batt_health').textContent = Object.keys(health).length
        ? Object.entries(health).map(([k, v]) => `${k}: ${v}`).join(', ') : 'NA';

    const badgeEl = document.getElementById('battery_state_badge');
    const locked = !!payload.locked_working;
    if (locked) {
        setStatusBox(badgeEl, true, 'GOOD (locked)');
    } else if (noFrames) {
        badgeEl.classList.remove('good', 'error');
        badgeEl.classList.add('na');
        badgeEl.textContent = 'NA';
    } else {
        setStatusBox(badgeEl, !!payload.working, payload.working ? 'GOOD' : 'ERROR');
    }

    document.getElementById('battery_message').textContent = payload.message || '--';
}

socket.on('battery_data', renderBattery);

function testBattery() {
    document.getElementById('battery_message').textContent = 'Reading...';
    fetch('/battery/read')
        .then(r => r.json())
        .then(renderBattery)
        .catch(err => {
            document.getElementById('battery_message').textContent = 'Fetch error: ' + err.message;
        });
}

// ========== DC OUT TAB ==========
function saveDcOutPorts() {
    const ports = ['port1', 'port2', 'port3'];
    const results = {};
    for (const p of ports) {
        const checked = document.querySelector(`input[name="${p}"]:checked`);
        if (!checked) {
            alert('Please answer all three DC out port questions before saving.');
            return;
        }
        results[p] = checked.value;
    }

    Promise.all(ports.map(p => fetch('/dc_out/save_port', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ port: p, result: results[p] })
    })))
    .then(() => {
        document.getElementById('dcOutSavedMsg').textContent = '\u2705 DC out results saved.';
    })
    .catch(err => alert('Error saving DC out results: ' + err.message));
}

function confirmBackupTest(confirmedOff) {
    const resultEl = document.getElementById('backupTestResult');

    if (!confirmedOff) {
        resultEl.textContent = 'Please turn off the charger output / remove AC input to continue this test.';
        return;
    }

    resultEl.textContent = 'Polling battery for Discharging / Disconnected state (up to 20s)...';

    fetch('/dc_out/backup/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirmed_off: true })
    })
    .then(r => r.json())
    .then(payload => {
        if (payload.status === 'waiting') {
            resultEl.textContent = payload.message;
            return;
        }
        const result = payload.result || {};
        if (result.result === 'pass') {
            resultEl.textContent = `\u2705 Battery backup confirmed - Discharging / disconnected after ${result.elapsed_s}s.`;
        } else if (result.result === 'na') {
            resultEl.textContent = `\u26a0\ufe0f No battery CAN frames received (NA) - check CAN1 status and battery wiring before retrying.`;
        } else {
            resultEl.textContent = `\u274c Timed out waiting for Discharging / disconnected state ` +
                `(last seen: state=${result.observed_battery_state ?? 'NA'}, charger=${result.observed_charger_connected ?? 'NA'}). ` +
                `Confirm AC/charger is actually off, then try again.`;
        }
    })
    .catch(err => {
        resultEl.textContent = 'Error running backup test: ' + err.message;
    });
}

// ========== INDICATOR TAB (pushbutton) ==========
socket.on('button_status', function (data) {
    const dot = document.getElementById('pushIndicatorDot');
    const label = document.getElementById('pushbuttonStatus');
    if (!dot || !label) return;

    dot.classList.remove('pressed-working', 'pressed-error');
    if (data.status === 'working') {
        dot.classList.add('pressed-working');
    } else if (data.status === 'error') {
        dot.classList.add('pressed-error');
    }
    label.textContent = `${data.label || '--'} - ${data.status === 'na' ? 'NA (no GPIO on this host)' : data.status.toUpperCase()}`;
});

// ========== QC MODAL ==========
function openQCModal() {
    document.getElementById('qcResult').innerText = '';
    document.getElementById('qcModal').style.display = 'block';
    document.getElementById('qcResultsList').innerHTML = '<p>Loading...</p>';
    document.getElementById('qcSummaryBanner')?.remove();

    fetch('/get_last_log').then(r => r.json()).then(logData => {
        const items = [];

        const sys = logData['system-check'] || {};
        items.push({ label: `CPU Usage: ${sys['cpu-usage']}`, ok: sys['cpu-usage'] !== null && sys['cpu-usage'] !== undefined });
        items.push({ label: `Temperature: ${sys['temperature']}`, ok: sys['temperature'] !== null && sys['temperature'] !== undefined });
        items.push({ label: `Humidity: ${sys['humidity']}`, ok: sys['humidity'] !== null && sys['humidity'] !== undefined });

        const insp = logData['inspection-status'] || {};
        items.push({ label: `Visual Inspection: ${insp.visual}`, ok: insp.visual === 'yes' });
        items.push({ label: `Electrical Inspection: ${insp.electrical}`, ok: insp.electrical === 'yes' });

        const ch = logData['charger-status'] || {};
        items.push({ label: `Charger Interface: ${ch.message}`, ok: ch.working === true });

        // Battery QC uses the session-latched verdict, not the instantaneous one -
        // so the deliberate charger-disconnect during the backup test doesn't
        // retroactively fail a battery interface that already proved itself.
        const batt = logData['battery-status'] || {};
        items.push({ label: `Battery Interface: ${batt.message}`, ok: batt.locked_working === true });

        const dcOut = logData['dc-output-status'] || {};
        for (const [k, v] of Object.entries(dcOut)) {
            items.push({ label: `DC Out ${k}: ${v}`, ok: v === 'pass' });
        }

        const backup = logData['battery-backup-status'] || {};
        items.push({ label: `Battery Backup Test: ${backup.result}`, ok: backup.result === 'pass' });

        const indicator = logData['indicator-status'] || {};
        items.push({ label: `Pushbutton Indicator: ${indicator.pushbutton}`, ok: indicator.pushbutton === 'working' });

        const can = logData['can-status'] || {};
        items.push({ label: `CAN1 Uplink: ${can.state} / ${can.health}`, ok: can.state === 'UP' && can.health === 'OK' });

        const eepromStat = logData['eeprom-status'] || {};
        items.push({ label: `EEPROM (0x59): ${eepromStat.present ? 'GOOD' : 'ERROR'}`, ok: !!eepromStat.present });

        let html = '<ul>';
        const failed = [];
        items.forEach(it => {
            const mark = it.ok ? '\u2705' : '\u274c';
            html += `<li><strong>${it.label}</strong> ${mark}</li>`;
            if (!it.ok) failed.push(it.label);
        });
        html += '</ul>';

        const allOk = failed.length === 0;
        const banner = document.createElement('div');
        banner.id = 'qcSummaryBanner';
        banner.style.padding = '10px';
        banner.style.borderRadius = '6px';
        banner.style.marginBottom = '10px';
        banner.style.textAlign = 'center';

        if (allOk) {
            banner.innerText = '\u2705 All tests passed - ready to confirm QC.';
            banner.style.backgroundColor = '#00c853';
            banner.style.color = 'white';
            document.getElementById('qcTitle').innerText = 'QC PASSED';
            document.getElementById('qcResult').setAttribute('data-status', 'passed');
        } else {
            banner.innerText = '\u274c Some tests failed or incomplete - review before confirming.';
            banner.style.backgroundColor = '#ff4c4c';
            banner.style.color = 'white';
            document.getElementById('qcTitle').innerText = 'QC FAILED';
            document.getElementById('qcResult').setAttribute('data-status', 'failed');
        }

        document.getElementById('qcResultsList').innerHTML = html;
        document.getElementById('qcModal').querySelector('.modal-content').prepend(banner);
        document.getElementById('qcModal').dataset.failed = JSON.stringify(failed);
    }).catch(err => {
        console.error('QC load error:', err);
        document.getElementById('qcResultsList').innerHTML = '<p style="color:red;">Failed to load test results.</p>';
    });
}

function closeQCModal() {
    document.getElementById('qcModal').style.display = 'none';
}

function confirmQC() {
    const status = document.getElementById('qcResult').getAttribute('data-status') || 'failed';
    const failed = JSON.parse(document.getElementById('qcModal').dataset.failed || '[]');

    if (status === 'failed' && failed.length === 0) {
        if (!confirm('QC is marked FAILED but no failing items were detected. Proceed to write FAILED QC anyway?')) return;
    }
    if (status === 'failed' && failed.length > 0) {
        if (!confirm('QC failures detected:\n\n' + failed.join('\n') + '\n\nProceed to save QC as FAILED?')) return;
    }

    fetch('/get_test_info')
        .then(r => r.json())
        .then(info => {
            const payload = {
                uuid: info.pcbserial || 'UNKNOWN',
                hw: info.modelnumber || 'UNKNOWN',
                timestamp: new Date().toISOString(),
                qc_status: (status === 'passed') ? 'PASSED' : 'FAILED',
                qc_fail_reasons: failed,
                full_log: null
            };
            return fetch('/write_eeprom_full', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        })
        .then(r => r.json())
        .then(res => {
            if (res.status === 'success') {
                alert('QC recorded to EEPROM: ' + res.device_info.qc_status);
                const qcFinalStatus = (status === 'passed') ? 'PASSED' : 'FAILED';
                socket.emit('qc_status_update', { qc_status: qcFinalStatus, qc_fail_reasons: failed });
                closeQCModal();
            } else {
                alert('Failed to write EEPROM: ' + (res.message || JSON.stringify(res)));
            }
        })
        .catch(err => alert('Error while confirming QC: ' + err));
}

// ========== DEVICE INFO MODAL ==========
function buildNestedList(obj) {
    let html = '<ul style="list-style-type:none; padding-left:0; text-align:left;">';
    for (const key in obj) {
        const val = obj[key];
        if (val && typeof val === 'object' && !Array.isArray(val)) {
            html += `<li style="padding:6px 0;"><strong>${key}</strong><ul style="list-style-type:none; padding-left:15px; margin-top:5px;">`;
            for (const subKey in val) {
                html += `<li style="padding:3px 0;"><strong>${subKey}:</strong> ${val[subKey]}</li>`;
            }
            html += '</ul></li>';
        } else if (Array.isArray(val)) {
            html += `<li style="padding:6px 0;"><strong>${key}:</strong><ul style="list-style-type:disc; padding-left:20px;">`;
            val.forEach(item => { html += `<li>${item}</li>`; });
            html += '</ul></li>';
        } else {
            html += `<li style="padding:6px 0; border-bottom:1px solid #333;"><strong>${key}:</strong> ${val}</li>`;
        }
    }
    html += '</ul>';
    return html;
}

function showDeviceInfo() {
    fetch('/device_info')
        .then(res => res.json())
        .then(data => {
            const modal = document.getElementById('deviceInfoModal');
            const content = document.getElementById('deviceInfoData');

            if (data.status !== 'success') {
                content.innerHTML = `<p style="color:red;">Error: ${data.message || 'Unknown error'}</p>`;
                modal.style.display = 'block';
                return;
            }

            const dev = data.device_info || {};
            const log = data.log_report || {};

            let html = '<h3 style="margin-bottom:5px;">Device Info</h3><ul style="list-style-type:none; padding-left:0;">';
            if (Object.keys(dev).length === 0) {
                html += '<li>(No device info available)</li>';
            } else {
                Object.keys(dev).forEach(key => {
                    html += `<li style="padding:6px 0; border-bottom:1px solid #333;"><strong>${key}:</strong> ${dev[key]}</li>`;
                });
            }
            html += '</ul><br><h3 style="margin-bottom:5px;">Test Log</h3>';
            html += Object.keys(log).length === 0 ? '<p>(No test log available)</p>' : buildNestedList(log);

            content.innerHTML = html;
            modal.style.display = 'block';
        })
        .catch(err => {
            console.error('Device Info Fetch Error:', err);
            document.getElementById('deviceInfoData').innerHTML = '<p style="color:red;">Error fetching device info.</p>';
            document.getElementById('deviceInfoModal').style.display = 'block';
        });
}

function closeDeviceInfo() {
    document.getElementById('deviceInfoModal').style.display = 'none';
}
