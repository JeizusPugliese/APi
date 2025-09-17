document.addEventListener("DOMContentLoaded", () => {
    const userRole = localStorage.getItem('userRole');
    const token = localStorage.getItem('token');

    if (userRole !== 'admin') return;

    // Cambia a tabla
    const usuariosTableBody = document.getElementById('usuariosTableBody');
    const adminUsuarioModal = document.getElementById('adminUsuarioModal');
    const adminUsuarioNombre = document.getElementById('adminUsuarioNombre');
    const sensoresUsuarioList = document.getElementById('sensoresUsuarioList');
    const adminAddSensorForm = document.getElementById('adminAddSensorForm');
    const adminSensorTipo = document.getElementById('adminSensorTipo');
    const adminRefreshBtn = document.getElementById('refresh-btn');
    const topLoader = document.getElementById('topLoader');
    const totalUsuariosEl = document.getElementById('totalUsuarios');
    const totalSensoresUsuarioEl = document.getElementById('totalSensoresUsuario');
    const userSearchInput = document.getElementById('userSearch');
    const userSearchBtn = document.getElementById('userSearchBtn');
    let usuarioSeleccionado = { id: null, nombre: '' };

    const setTopLoading = (on) => { if (topLoader) topLoader.classList.toggle('active', !!on); };

    // -- NUEVO: función para cargar usuarios (reutilizable) --
    async function cargarUsuariosAdmin() {
        try {
            setTopLoading(true);
            usuariosTableBody.innerHTML = '<tr><td colspan="6" style="text-align:center;">Cargando usuarios...</td></tr>';
            const res = await axios.get('https://apigreentech-e7g6a3e8hbbwdxf8.brazilsouth-01.azurewebsites.net/obtener_usuarios_admin', {
                headers: { Authorization: `Bearer ${token}` }
            });
            if (!res.data || !Array.isArray(res.data.usuarios)) {
                usuariosTableBody.innerHTML = '<tr><td colspan="6" style="color:red;">Respuesta inesperada de la API.</td></tr>';
                if (totalUsuariosEl) totalUsuariosEl.textContent = '0';
                return;
            }
            const usuarios = res.data.usuarios;
            usuariosTableBody.innerHTML = '';
            if (usuarios.length === 0) {
                usuariosTableBody.innerHTML = '<tr><td colspan="3" style="color:#888;text-align:center;">No hay usuarios registrados.</td></tr>';
            } else {
                usuarios.forEach(usuario => {
                    // Oculta admin
                    if ((usuario.rol || '').toLowerCase() === 'admin') return;
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${usuario.nombre}</td>
                        <td>${usuario.apellido || ''}</td>
                        <td>
                          <button class="admin-btn" data-id="${usuario.id}" data-nombre="${usuario.nombre} ${usuario.apellido || ''}">Administrar</button>
                        </td>
                    `;
                    usuariosTableBody.appendChild(tr);
                });
            }
            if (totalUsuariosEl) {
                // Excluye admins del conteo visual
                const totalNoAdmins = usuarios.filter(u => (u.rol || '').toLowerCase() !== 'admin').length;
                totalUsuariosEl.textContent = String(totalNoAdmins);
            }
        } catch (err) {
            let msg = 'Error al cargar usuarios.';
            if (err.response) {
                msg += ` [${err.response.status}] ${err.response.statusText}`;
                if (err.response.data && err.response.data.message) msg += `: ${err.response.data.message}`;
            } else if (err.request) {
                msg += ' No se recibió respuesta del servidor.';
            } else {
                msg += ' ' + err.message;
            }
            usuariosTableBody.innerHTML = `<tr><td colspan="6" style="color:red;">${msg}</td></tr>`;
            if (totalUsuariosEl) totalUsuariosEl.textContent = '0';
        } finally {
            setTopLoading(false);
        }
    }

    // -- Reemplaza la carga inline por la función --
    // axios.get(...).then(...).catch(...)  --> sustituido por:
    cargarUsuariosAdmin();

    // Cargar tipos de sensor en el select del modal admin
    async function cargarTipos() {
        try {
            const res = await axios.get('https://apigreentech-e7g6a3e8hbbwdxf8.brazilsouth-01.azurewebsites.net/tipo_sensor', {
                headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
            });
            const tipos = res.data?.data || [];
            adminSensorTipo.innerHTML = '<option value="" disabled selected>Seleccione tipo</option>';
            tipos.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.id;
                opt.textContent = `${t.id} - ${t.nombre}`;
                adminSensorTipo.appendChild(opt);
            });
        } catch {
            adminSensorTipo.innerHTML = '<option value="" disabled selected>Error al cargar tipos</option>';
        }
    }

    // Render sensores con mejor diseño y botones destacados
    function renderSensores(sensores = []) {
        sensoresUsuarioList.innerHTML = '';
        if (!Array.isArray(sensores) || sensores.length === 0) {
            sensoresUsuarioList.innerHTML = '<div style="color:#888;text-align:center;">No tiene sensores registrados.</div>';
            return;
        }
        sensores.forEach(sensor => {
            const estado = sensor.estado && sensor.estado.toLowerCase() === 'on' ? 'Encendido' : 'Apagado';
            const estadoColor = estado === 'Encendido' ? '#43aa8b' : '#adb5bd';
            let tiempoEncendido = '--';
            if (estado === 'Encendido') {
                const horas = Math.floor(Math.random() * 5) + 1;
                const minutos = Math.floor(Math.random() * 60);
                tiempoEncendido = `${horas}h ${minutos}m`;
            }
            // Diseño visual mejorado para cada sensor, mostrando el ID
            const item = document.createElement('div');
            item.className = 'sensor-admin-item';
            item.style = `
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 1rem 1.2rem;
                border-radius: 12px;
                background: #fff;
                box-shadow: 0 2px 8px #4361ee12;
                margin-bottom: 1rem;
                gap: 1rem;
            `;
            item.innerHTML = `
                <div style="flex:2;display:flex;flex-direction:column;">
                  <span class="sensor-nombre" style="font-weight:600;font-size:1.08rem;color:#222;">
                    <span style="color:#888;font-size:0.98rem;font-weight:400;">ID: ${sensor.id}</span>
                    &nbsp;${sensor.nombre_sensor || 'Sensor'}
                  </span>
                  <span style="font-size:0.97rem;color:#4361ee;font-weight:500;">(${sensor.id_tipo_sensor} - ${sensor.tipo_sensor || 'Tipo desconocido'})</span>
                  <span style="font-size:0.93rem;color:#888;">Ref: <b>${sensor.referencia || '--'}</b></span>
                </div>
                <div class="sensor-estado" style="font-weight:700;min-width:90px;text-align:center;color:${estadoColor};font-size:1.01rem;">
                  ${estado}
                </div>
                <div style="font-size:0.92rem;color:#888;min-width:120px;">Tiempo encendido: <span>${tiempoEncendido}</span></div>
                <div style="display:flex;gap:0.5rem;">
                  <button class="btn-toggle-sensor btn" data-id="${sensor.id}" title="Encender/Apagar" style="background:#4361ee;color:#fff;transition:background 0.2s;padding:0.5rem 0.8rem;border-radius:7px;"><i class="fas fa-power-off"></i></button>
                  <button class="btn-calibrar-sensor btn" data-id="${sensor.id}" title="Calibrar" style="background:#ffd166;color:#222;transition:background 0.2s;padding:0.5rem 0.8rem;border-radius:7px;"><i class="fas fa-tools"></i></button>
                  <button class="btn-eliminar-sensor btn" data-id="${sensor.id}" title="Eliminar" style="background:#e63946;color:#fff;transition:background 0.2s;padding:0.5rem 0.8rem;border-radius:7px;"><i class="fas fa-trash"></i></button>
                </div>
            `;
            sensoresUsuarioList.appendChild(item);
        });
    }

    // Función para renderizar sensores del usuario en el modal de administración
    function renderSensoresUsuario(sensores) {
        const contenedor = document.getElementById('sensoresUsuarioList');
        contenedor.innerHTML = '';
        if (!sensores || sensores.length === 0) {
            contenedor.innerHTML = '<div style="text-align:center;color:#888;">No hay sensores asignados a este usuario.</div>';
            return;
        }
        sensores.forEach(sensor => {
            // Estado visual
            const online = sensor.estado && sensor.estado.toLowerCase() === 'online';
            const colorEstado = online ? '#43aa8b' : '#adb5bd';
            const textoEstado = online ? 'Online' : 'Offline';
            const tiempoEncendido = sensor.tiempo_encendido !== undefined && sensor.tiempo_encendido !== null
                ? `${sensor.tiempo_encendido} min`
                : '--';

            const div = document.createElement('div');
            div.className = 'admin-sensor-row';
            div.style = 'display:flex;align-items:center;gap:1.2rem;padding:0.7rem 0;border-bottom:1px solid #eee;';
            div.innerHTML = `
                <div style="flex:1;">
                    <b>${sensor.nombre_sensor}</b> <span style="color:#888;font-size:0.95em;">(${sensor.tipo_sensor})</span>
                    <div style="font-size:0.95em;color:#888;">Ref: ${sensor.referencia || '—'}</div>
                </div>
                <div style="text-align:center;">
                    <span class="dot" style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${colorEstado};margin-right:6px;"></span>
                    <span style="font-weight:600;color:${colorEstado};">${textoEstado}</span>
                    <div style="font-size:0.85em;color:#43aa8b;">Encendido: ${tiempoEncendido}</div>
                </div>
                <div style="display:flex;gap:0.5rem;">
                  <button class="btn-toggle-sensor btn" data-id="${sensor.id}" title="Encender/Apagar" style="background:#4361ee;color:#fff;transition:background 0.2s;padding:0.5rem 0.8rem;border-radius:7px;"><i class="fas fa-power-off"></i></button>
                  <button class="btn-calibrar-sensor btn" data-id="${sensor.id}" title="Calibrar" style="background:#ffd166;color:#222;transition:background 0.2s;padding:0.5rem 0.8rem;border-radius:7px;"><i class="fas fa-tools"></i></button>
                  <button class="btn-eliminar-sensor btn" data-id="${sensor.id}" title="Eliminar" style="background:#e63946;color:#fff;transition:background 0.2s;padding:0.5rem 0.8rem;border-radius:7px;"><i class="fas fa-trash"></i></button>
                </div>
            `;
            contenedor.appendChild(div);
        });
    }

    // --- Filtro local de usuarios ---
    function filtrarUsuarios(term) {
        const t = (term || '').toLowerCase().trim();
        const rows = usuariosTableBody.querySelectorAll('tr');
        rows.forEach(row => {
            const nombre = (row.cells[0]?.textContent || '').toLowerCase();
            const apellido = (row.cells[1]?.textContent || '').toLowerCase();
            row.style.display = (nombre.includes(t) || apellido.includes(t)) ? '' : 'none';
        });
    }
    if (userSearchInput) userSearchInput.addEventListener('input', (e) => filtrarUsuarios(e.target.value));
    if (userSearchBtn && userSearchInput) userSearchBtn.addEventListener('click', () => filtrarUsuarios(userSearchInput.value));

    // --- Actualización en tiempo real del modal de administración ---
    let adminSensorInterval = null;
    function iniciarActualizacionSensoresUsuario() {
        if (adminSensorInterval) clearInterval(adminSensorInterval);
        adminSensorInterval = setInterval(() => {
            if (adminUsuarioModal && getComputedStyle(adminUsuarioModal).display !== 'none' && usuarioSeleccionado.id) {
                cargarSensoresUsuario(usuarioSeleccionado.id);
            }
        }, 10000); // cada 10 segundos
    }
    function detenerActualizacionSensoresUsuario() {
        if (adminSensorInterval) clearInterval(adminSensorInterval);
    }

    // Abrir modal administrar usuario
    usuariosTableBody.addEventListener('click', async (e) => {
        const btn = e.target.closest('.admin-btn');
        if (!btn) return;
        const id = btn.getAttribute('data-id');
        const nombre = btn.getAttribute('data-nombre');
        usuarioSeleccionado = { id, nombre };
        adminUsuarioNombre.textContent = nombre;
        sensoresUsuarioList.innerHTML = '<div style="text-align:center;">Cargando sensores...</div>';
        adminUsuarioModal.style.display = 'flex';
        await cargarTipos();
        await cargarSensoresUsuario(id);
        iniciarActualizacionSensoresUsuario();
    });

    // Cerrar modal
    window.cerrarAdminUsuarioModal = function() {
        adminUsuarioModal.style.display = 'none';
        detenerActualizacionSensoresUsuario();
    };
    adminUsuarioModal.addEventListener('click', (e) => {
        if (e.target === adminUsuarioModal) {
            adminUsuarioModal.style.display = 'none';
            detenerActualizacionSensoresUsuario();
        }
    });

    // Cargar sensores de un usuario
    async function cargarSensoresUsuario(userId) {
        setTopLoading(true);
        sensoresUsuarioList.innerHTML = '<div style="text-align:center;">Cargando sensores...</div>';
        try {
            const res = await axios.get(`https://apigreentech-e7g6a3e8hbbwdxf8.brazilsouth-01.azurewebsites.net/sensores_usuario/${userId}`, {
                headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
            });
            renderSensores(res.data);
            renderSensoresUsuario(res.data);
            if (totalSensoresUsuarioEl) totalSensoresUsuarioEl.textContent = String(Array.isArray(res.data) ? res.data.length : 0);
        } catch (err) {
            sensoresUsuarioList.innerHTML = '<div style="color:red;text-align:center;">Error al cargar sensores.</div>';
            if (totalSensoresUsuarioEl) totalSensoresUsuarioEl.textContent = '0';
        } finally {
            setTopLoading(false);
        }
    }

    // -- Botón Actualizar (recarga usuarios o sensores del modal) --
    if (adminRefreshBtn) {
        adminRefreshBtn.addEventListener('click', async () => {
            const icon = adminRefreshBtn.querySelector('i');
            adminRefreshBtn.disabled = true;
            if (icon) icon.classList.add('fa-spin');
            setTopLoading(true);
            try {
                const modalAbierto = adminUsuarioModal && getComputedStyle(adminUsuarioModal).display !== 'none';
                if (modalAbierto && usuarioSeleccionado.id) {
                    await cargarSensoresUsuario(usuarioSeleccionado.id);
                } else {
                    await cargarUsuariosAdmin();
                }
                const lastUpdate = document.getElementById('last-update-text');
                if (lastUpdate) {
                    const ahora = new Date();
                    lastUpdate.textContent = `Última actualización: ${ahora.toLocaleTimeString()}`;
                }
            } finally {
                setTimeout(() => {
                    adminRefreshBtn.disabled = false;
                    if (icon) icon.classList.remove('fa-spin');
                    setTopLoading(false);
                }, 300);
            }
        });
    }

    // Cargar tipos de sensor en el select del modal admin
    async function cargarTipos() {
        try {
            const res = await axios.get('https://apigreentech-e7g6a3e8hbbwdxf8.brazilsouth-01.azurewebsites.net/tipo_sensor', {
                headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
            });
            const tipos = res.data?.data || [];
            adminSensorTipo.innerHTML = '<option value="" disabled selected>Seleccione tipo</option>';
            tipos.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.id;
                opt.textContent = `${t.id} - ${t.nombre}`;
                adminSensorTipo.appendChild(opt);
            });
        } catch {
            adminSensorTipo.innerHTML = '<option value="" disabled selected>Error al cargar tipos</option>';
        }
    }

    // Agregar sensor desde el modal admin (con referencia obligatoria)
    if (adminAddSensorForm) {
        adminAddSensorForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const nombre = document.getElementById('adminSensorName').value.trim();
            const tipo = adminSensorTipo.value;
            const referencia = document.getElementById('adminSensorRef').value;
            if (!usuarioSeleccionado.id) {
                Swal.fire('Error', 'Usuario no seleccionado', 'error');
                return;
            }
            if (!nombre || !tipo || !referencia) {
                Swal.fire('Error', 'Todos los campos son obligatorios', 'error');
                return;
            }
            try {
                setTopLoading(true);
                await axios.post('https://apigreentech-e7g6a3e8hbbwdxf8.brazilsouth-01.azurewebsites.net/add_sensor', {
                    nombre_sensor: nombre,
                    referencia: referencia,
                    id_tipo_sensor: Number(tipo),
                    id_usuario: Number(usuarioSeleccionado.id)
                }, {
                    headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
                });
                Swal.fire({
                    icon: 'success',
                    title: 'Sensor agregado',
                    showConfirmButton: false,
                    timer: 1200
                });
                adminAddSensorForm.reset();
                await cargarSensoresUsuario(usuarioSeleccionado.id);
            } catch (err) {
                Swal.fire('Error', 'No se pudo agregar el sensor', 'error');
            } finally {
                setTopLoading(false);
            }
        });
    }

    // Cerrar modal
    window.cerrarAdminUsuarioModal = function() {
        adminUsuarioModal.style.display = 'none';
    };
    adminUsuarioModal.addEventListener('click', (e) => {
        if (e.target === adminUsuarioModal) adminUsuarioModal.style.display = 'none';
    });

    // Acciones dentro del modal (encender/apagar/calibrar/eliminar)
    sensoresUsuarioList.addEventListener('click', async (e) => {
        const btnToggle = e.target.closest('.btn-toggle-sensor');
        const btnCalibrar = e.target.closest('.btn-calibrar-sensor');
        const btnEliminar = e.target.closest('.btn-eliminar-sensor');
        if (btnToggle) {
            const sensorId = btnToggle.getAttribute('data-id');
            btnToggle.classList.add('fa-spin');
            try {
                setTopLoading(true);
                await axios.post(`https://apigreentech-e7g6a3e8hbbwdxf8.brazilsouth-01.azurewebsites.net/toggle_sensor/${sensorId}`, {}, {
                    headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
                });
                Swal.fire({
                    icon: 'success',
                    title: 'Estado actualizado',
                    showConfirmButton: false,
                    timer: 1000
                });
                await cargarSensoresUsuario(usuarioSeleccionado.id);
            } catch (err) {
                Swal.fire('Error', 'No se pudo cambiar el estado', 'error');
            } finally {
                btnToggle.classList.remove('fa-spin');
                setTopLoading(false);
            }
        }
        if (btnCalibrar) {
            const sensorId = btnCalibrar.getAttribute('data-id');
            btnCalibrar.classList.add('fa-spin');
            try {
                setTopLoading(true);
                await axios.post(`https://apigreentech-e7g6a3e8hbbwdxf8.brazilsouth-01.azurewebsites.net/calibrar_sensor/${sensorId}`, {}, {
                    headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
                });
                Swal.fire({
                    icon: 'success',
                    title: 'Sensor calibrado',
                    showConfirmButton: false,
                    timer: 1000
                });
            } catch (err) {
                Swal.fire('Error', 'No se pudo calibrar el sensor', 'error');
            } finally {
                btnCalibrar.classList.remove('fa-spin');
                setTopLoading(false);
            }
        }
        if (btnEliminar) {
            const sensorId = btnEliminar.getAttribute('data-id');
            btnEliminar.classList.add('fa-spin');
            const confirm = await Swal.fire({
                title: '¿Eliminar sensor?',
                text: 'Esta acción no se puede deshacer',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Sí, eliminar',
                cancelButtonText: 'Cancelar'
            });
            if (!confirm.isConfirmed) {
                btnEliminar.classList.remove('fa-spin');
                return;
            }
            try {
                setTopLoading(true);
                await axios.delete(`https://apigreentech-e7g6a3e8hbbwdxf8.brazilsouth-01.azurewebsites.net/eliminar_sensor/${sensorId}`, {
                    headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
                });
                Swal.fire({
                    icon: 'success',
                    title: 'Sensor eliminado',
                    showConfirmButton: false,
                    timer: 1000
                });
                await cargarSensoresUsuario(usuarioSeleccionado.id);
            } catch (err) {
                Swal.fire('Error', 'No se pudo eliminar el sensor', 'error');
            } finally {
                btnEliminar.classList.remove('fa-spin');
                setTopLoading(false);
            }
        }
    });

    console.log("¿usuariosTableBody existe?", document.getElementById('usuariosTableBody'));
});
