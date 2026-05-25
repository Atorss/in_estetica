(function () {
    'use strict';

    var MESES = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ];
    var DIAS = ['Dom', 'Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab'];

    function rpc(route, params) {
        return fetch(route, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: params || {} }),
        }).then(function (r) { return r.json(); }).then(function (j) {
            if (j.error) throw j.error;
            return j.result;
        });
    }

    function el(html) {
        var t = document.createElement('template');
        t.innerHTML = html.trim();
        return t.content.firstChild;
    }

    function fmtFecha(yyyymmdd) {
        var parts = yyyymmdd.split('-');
        var d = new Date(parts[0], parts[1] - 1, parts[2]);
        return DIAS[d.getDay()] + ' ' + parts[2] + ' ' + MESES[d.getMonth()].toLowerCase();
    }

    function NutriWizard(root) {
        this.root = root;
        this.state = {
            step: 1,
            tipoCitaId: null,
            tipoCitaNombre: null,
            tipoCitaDuracion: null,
            tipoCitaPrecio: null,
            diasDisponibles: [],
            mesOffset: 0,
            fecha: null,
            slotId: null,
            slotHora: null,
            slotDoctor: null,
        };
        this.bind();
        this.loadTipos();
    }

    NutriWizard.prototype.bind = function () {
        var self = this;
        this.root.addEventListener('click', function (e) {
            var back = e.target.closest('[data-action="back"]');
            if (back) {
                self.goto(Math.max(1, self.state.step - 1));
            }
        });
        var submit = this.root.querySelector('#nutri_wizard_submit');
        if (submit) submit.addEventListener('click', this.submit.bind(this));
        var reset = this.root.querySelector('#nutri_wizard_reset');
        if (reset) reset.addEventListener('click', this.reset.bind(this));

        var cedulaInput = this.root.querySelector('[name="cedula"]');
        if (cedulaInput) {
            var lookup = this.lookupPaciente.bind(this);
            cedulaInput.addEventListener('blur', lookup);
            cedulaInput.addEventListener('change', lookup);
        }
    };

    NutriWizard.prototype.lookupPaciente = function () {
        var self = this;
        var input = this.root.querySelector('[name="cedula"]');
        var ced = (input.value || '').trim();
        if (!/^\d{8,15}$/.test(ced)) return;
        if (this._lastLookup === ced) return;
        this._lastLookup = ced;

        var hint = this.root.querySelector('#nutri_wizard_msg');
        input.classList.add('is-loading');

        rpc('/agendar/buscar-paciente', { cedula: ced }).then(function (res) {
            input.classList.remove('is-loading');
            if (res && res.found) {
                self._setIfEmpty('nombre', res.nombre);
                self._setIfEmpty('apellido', res.apellido);
                self._setIfEmpty('email', res.email);
                self._setIfEmpty('telefono', res.telefono);
                if (hint) {
                    hint.textContent = 'Encontramos tu registro previo. Verifica los datos.';
                    hint.className = 'nutri-wizard__msg is-success';
                    hint.style.display = 'block';
                }
            }
        }).catch(function () {
            input.classList.remove('is-loading');
        });
    };

    NutriWizard.prototype._setIfEmpty = function (name, value) {
        if (!value) return;
        var el = this.root.querySelector('[name="' + name + '"]');
        if (el && !el.value.trim()) el.value = value;
    };

    NutriWizard.prototype.goto = function (step) {
        this.state.step = step;
        this.root.querySelectorAll('.nutri-wizard__step').forEach(function (s) {
            s.classList.toggle('is-active', parseInt(s.dataset.step, 10) === step);
        });
        this.root.querySelectorAll('.nutri-wizard__step-pill').forEach(function (p) {
            var s = parseInt(p.dataset.step, 10);
            p.classList.toggle('is-active', s === step);
            p.classList.toggle('is-done', s < step);
        });
    };

    NutriWizard.prototype.loadTipos = function () {
        var self = this;
        var box = this.root.querySelector('#nutri_tipos');
        rpc('/agendar/tipos').then(function (tipos) {
            box.innerHTML = '';
            if (!tipos || !tipos.length) {
                box.innerHTML = '<p class="nutri-wizard__empty">No hay tipos de cita configurados aun.</p>';
                return;
            }
            tipos.forEach(function (t) {
                var node = el(
                    '<button type="button" class="nutri-wizard__tipo" data-id="' + t.id + '">' +
                        '<div class="nutri-wizard__tipo-head">' +
                            '<span class="nutri-wizard__tipo-name">' + t.name + '</span>' +
                            '<span class="nutri-wizard__tipo-dur">' + t.duracion_min + ' min</span>' +
                        '</div>' +
                        (t.descripcion ? '<p class="nutri-wizard__tipo-desc">' + t.descripcion + '</p>' : '') +
                        '<span class="nutri-wizard__tipo-arrow"><i class="fa fa-arrow-right"></i></span>' +
                    '</button>'
                );
                node.addEventListener('click', function () {
                    self.state.tipoCitaId = t.id;
                    self.state.tipoCitaNombre = t.name;
                    self.state.tipoCitaDuracion = t.duracion_min;
                    self.state.tipoCitaPrecio = t.precio;
                    self.loadDias();
                });
                box.appendChild(node);
            });
        }).catch(function () {
            box.innerHTML = '<p class="nutri-wizard__empty">Error cargando tipos.</p>';
        });
    };

    NutriWizard.prototype.loadDias = function () {
        var self = this;
        var box = this.root.querySelector('#nutri_calendar');
        box.innerHTML = '<div class="nutri-wizard__loading"><i class="fa fa-circle-o-notch fa-spin"></i></div>';
        this.goto(2);
        rpc('/agendar/dias-disponibles', { tipo_cita_id: this.state.tipoCitaId }).then(function (dias) {
            self.state.diasDisponibles = dias || [];
            self.state.mesOffset = 0;
            self.renderCalendar();
        }).catch(function () {
            box.innerHTML = '<p class="nutri-wizard__empty">Error cargando dias.</p>';
        });
    };

    NutriWizard.prototype.renderCalendar = function () {
        var self = this;
        var box = this.root.querySelector('#nutri_calendar');
        var disp = new Set(this.state.diasDisponibles);

        var today = new Date();
        today.setHours(0, 0, 0, 0);
        var mes = new Date(today.getFullYear(), today.getMonth() + this.state.mesOffset, 1);

        var firstDow = mes.getDay();
        var daysInMonth = new Date(mes.getFullYear(), mes.getMonth() + 1, 0).getDate();

        var html = '<div class="nutri-cal__head">' +
            '<button type="button" class="nutri-cal__nav" data-dir="-1" ' + (this.state.mesOffset <= 0 ? 'disabled' : '') + '><i class="fa fa-chevron-left"></i></button>' +
            '<span class="nutri-cal__title">' + MESES[mes.getMonth()] + ' ' + mes.getFullYear() + '</span>' +
            '<button type="button" class="nutri-cal__nav" data-dir="1"><i class="fa fa-chevron-right"></i></button>' +
        '</div>';

        html += '<div class="nutri-cal__dow">';
        ['L', 'M', 'X', 'J', 'V', 'S', 'D'].forEach(function (d) {
            html += '<span>' + d + '</span>';
        });
        html += '</div>';

        html += '<div class="nutri-cal__grid">';
        // Lunes como primer dia: domingo=0 → 6, lunes=1 → 0...
        var leadingBlanks = (firstDow + 6) % 7;
        for (var i = 0; i < leadingBlanks; i++) {
            html += '<span class="nutri-cal__cell is-blank"></span>';
        }
        for (var d = 1; d <= daysInMonth; d++) {
            var dt = new Date(mes.getFullYear(), mes.getMonth(), d);
            var key = dt.getFullYear() + '-' + String(dt.getMonth() + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0');
            var classes = 'nutri-cal__cell';
            var clickable = false;
            if (dt < today) classes += ' is-past';
            else if (disp.has(key)) { classes += ' is-available'; clickable = true; }
            else classes += ' is-disabled';
            html += '<button type="button" class="' + classes + '" ' + (clickable ? 'data-date="' + key + '"' : 'disabled') + '>' + d + '</button>';
        }
        html += '</div>';

        box.innerHTML = html;

        box.querySelectorAll('[data-dir]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                self.state.mesOffset += parseInt(btn.dataset.dir, 10);
                if (self.state.mesOffset < 0) self.state.mesOffset = 0;
                self.renderCalendar();
            });
        });
        box.querySelectorAll('[data-date]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                self.state.fecha = btn.dataset.date;
                self.loadSlots();
            });
        });
    };

    NutriWizard.prototype.loadSlots = function () {
        var self = this;
        var box = this.root.querySelector('#nutri_slots');
        var hint = this.root.querySelector('#nutri_slots_hint');
        hint.textContent = fmtFecha(this.state.fecha);
        box.innerHTML = '<div class="nutri-wizard__loading"><i class="fa fa-circle-o-notch fa-spin"></i></div>';
        this.goto(3);
        rpc('/agendar/slots', {
            tipo_cita_id: this.state.tipoCitaId,
            fecha: this.state.fecha,
        }).then(function (slots) {
            if (!slots || !slots.length) {
                box.innerHTML = '<p class="nutri-wizard__empty">No quedan horarios disponibles ese dia.</p>';
                return;
            }
            box.innerHTML = '';
            slots.forEach(function (s) {
                var node = el(
                    '<button type="button" class="nutri-wizard__slot" data-id="' + s.id + '">' +
                        '<span class="nutri-wizard__slot-hora">' + s.hora + '</span>' +
                        '<span class="nutri-wizard__slot-doc">' + s.doctor_name + '</span>' +
                    '</button>'
                );
                node.addEventListener('click', function () {
                    self.state.slotId = s.id;
                    self.state.slotHora = s.hora;
                    self.state.slotDoctor = s.doctor_name;
                    self.showSummary();
                    self.goto(4);
                });
                box.appendChild(node);
            });
        }).catch(function () {
            box.innerHTML = '<p class="nutri-wizard__empty">Error cargando horarios.</p>';
        });
    };

    NutriWizard.prototype.showSummary = function () {
        var s = this.state;
        var precio = s.tipoCitaPrecio ? ('$ ' + s.tipoCitaPrecio.toFixed(2)) : '';
        this.root.querySelector('#nutri_summary').innerHTML =
            '<div class="nutri-wizard__sum-row"><span>Consulta</span><strong>' + s.tipoCitaNombre + '</strong></div>' +
            '<div class="nutri-wizard__sum-row"><span>Fecha</span><strong>' + fmtFecha(s.fecha) + '</strong></div>' +
            '<div class="nutri-wizard__sum-row"><span>Hora</span><strong>' + s.slotHora + '</strong></div>' +
            '<div class="nutri-wizard__sum-row"><span>Profesional</span><strong>' + s.slotDoctor + '</strong></div>' +
            (precio ? '<div class="nutri-wizard__sum-row"><span>Tarifa</span><strong>' + precio + '</strong></div>' : '');
    };

    NutriWizard.prototype.submit = function () {
        var self = this;
        var btn = this.root.querySelector('#nutri_wizard_submit');
        var msg = this.root.querySelector('#nutri_wizard_msg');
        var get = function (n) { return (self.root.querySelector('[name="' + n + '"]').value || '').trim(); };

        var payload = {
            turno_id: this.state.slotId,
            tipo_cita_id: this.state.tipoCitaId,
            cedula: get('cedula'),
            nombre: get('nombre'),
            apellido: get('apellido'),
            email: get('email'),
            telefono: get('telefono'),
            notas: get('notas'),
        };

        if (!payload.cedula || !payload.nombre || !payload.apellido || !payload.email || !payload.telefono) {
            self._msg(msg, 'Completa todos los campos obligatorios.', 'error');
            return;
        }

        btn.disabled = true;
        btn.innerHTML = '<i class="fa fa-circle-o-notch fa-spin me-2"></i>Reservando...';
        msg.style.display = 'none';

        rpc('/agendar/reservar', payload).then(function (res) {
            if (res && res.success) {
                self.showSuccess(res);
            } else {
                self._msg(msg, (res && res.message) || 'Error en la reserva.', 'error');
            }
        }).catch(function () {
            self._msg(msg, 'Error de conexion.', 'error');
        }).finally(function () {
            btn.disabled = false;
            btn.innerHTML = 'Confirmar reserva';
        });
    };

    NutriWizard.prototype._msg = function ($el, text, type) {
        $el.textContent = text;
        $el.className = 'nutri-wizard__msg is-' + type;
        $el.style.display = 'block';
    };

    NutriWizard.prototype.showSuccess = function (res) {
        var body = this.root.querySelector('#nutri_success_body');
        body.innerHTML =
            '<p>Tu reserva <strong>' + (res.ref || '') + '</strong> esta registrada.</p>' +
            '<div class="nutri-wizard__sum-row"><span>Cita</span><strong>' + (res.tipo || '') + '</strong></div>' +
            '<div class="nutri-wizard__sum-row"><span>Fecha</span><strong>' + (res.fecha || '') + ' &middot; ' + (res.hora || '') + '</strong></div>' +
            '<div class="nutri-wizard__sum-row"><span>Profesional</span><strong>' + (res.doctor || '') + '</strong></div>' +
            '<p class="nutri-wizard__hint mt-3">Te llamaremos para confirmar. Si necesitas cambiar el horario, escribenos por WhatsApp.</p>';

        // Mostrar el step 5 mediante un truco: lo hacemos visible aunque no este en los pills
        this.root.querySelectorAll('.nutri-wizard__step').forEach(function (s) {
            s.classList.toggle('is-active', s.dataset.step === '5');
        });
        this.root.querySelectorAll('.nutri-wizard__step-pill').forEach(function (p) {
            p.classList.add('is-done');
            p.classList.remove('is-active');
        });
    };

    NutriWizard.prototype.reset = function () {
        this.state = {
            step: 1, tipoCitaId: null, tipoCitaNombre: null,
            tipoCitaDuracion: null, tipoCitaPrecio: null,
            diasDisponibles: [], mesOffset: 0, fecha: null,
            slotId: null, slotHora: null, slotDoctor: null,
        };
        this.root.querySelectorAll('[name]').forEach(function (i) { i.value = ''; });
        this.goto(1);
        this.loadTipos();
    };

    function boot() {
        var root = document.getElementById('nutri_wizard');
        if (!root || root.dataset.booted) return;
        root.dataset.booted = '1';
        new NutriWizard(root);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        setTimeout(boot, 200);
    }
    window.addEventListener('load', function () { setTimeout(boot, 400); });
})();
