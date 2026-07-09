import streamlit as st
from supabase import create_client, Client
import datetime

# ==============================================================================
# 1. CONFIGURACIÓN Y CONEXIÓN BÓVEDA DE DATOS (SUPABASE)
# ==============================================================================
st.set_page_config(page_title="Fondo Familiar", page_icon="📊", layout="wide")

@st.cache_resource
def inicializar_conexion_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = inicializar_conexion_supabase()

if 'usuario_actual' not in st.session_state:
    st.session_state['usuario_actual'] = None

# ==============================================================================
# 2. CAPA DE AUTENTICACIÓN
# ==============================================================================
def pantalla_autenticacion():
    st.title("🔐 Acceso al Sistema - Fondo Familiar")
    st.write("Bienvenido. Ingrese sus credenciales autorizadas.")
    
    col_login, _ = st.columns([1, 2])
    with col_login:
        correo = st.text_input("Correo electrónico", key="login_correo").strip().lower()
        contrasena = st.text_input("Contraseña de seguridad", type="password", key="login_pass")
        
        if st.button("Iniciar Sesión", key="btn_login"):
            respuesta = supabase.table("usuarios").select("*").eq("correo", correo).execute()
            if len(respuesta.data) > 0:
                usuario_db = respuesta.data[0]
                if usuario_db['contrasena_cifrada'] == contrasena:
                    if usuario_db.get('activo', True) == True:
                        st.session_state['usuario_actual'] = usuario_db
                        st.success(f"Ingreso autorizado para {usuario_db['nombre']}.")
                        st.rerun()
                    else:
                        st.error("🔒 Acceso denegado. Esta cuenta ha sido suspendida/bloqueada.")
                else:
                    st.error("Contraseña incorrecta. Verifique sus datos.")
            else:
                st.error("El usuario ingresado no se encuentra registrado.")

# ==============================================================================
# 3. CAPA DE APLICACIÓN - PANEL INTERNO PRINCIPAL
# ==============================================================================
def pantalla_principal():
    usuario = st.session_state['usuario_actual']
    
    st.sidebar.title(f"Hola, {usuario['nombre']} 👋")
    st.sidebar.info(f"**Rol:** {usuario['rol']}")
    if st.sidebar.button("Cerrar Sesión", key="btn_logout"):
        st.session_state['usuario_actual'] = None 
        st.rerun()
        
    st.title("📊 Sistema Integral de Gestión Financiera")
    
    es_admin = usuario['rol'] == "Administrador"
    es_revisor = usuario['rol'] in ["Administrador", "Revisor", "Tesorero"]
    es_tesorero_admin = usuario['rol'] in ["Administrador", "Tesorero"]
    
    nombres_pestanas = ["Resumen", "💸 Pagar", "📜 Historial", "🤝 Préstamos", "📅 Cierre Anual"]
    if es_revisor:
        nombres_pestanas.append("✅ Revisión Pagos")
    if es_admin:
        nombres_pestanas.append("👤 Gestión Usuarios")
    if es_tesorero_admin:
        nombres_pestanas.append("⚙️ Asignar Cupos")
        
    tabs = st.tabs(nombres_pestanas)
    
    # --- PESTAÑA 0: RESUMEN FINANCIERO ---
    with tabs[0]:
        st.subheader("Estado de tu cuenta")
        respuesta_ciclo = supabase.table("configuracion_ciclo").select("*").eq("anio", 2026).execute()
        
        if len(respuesta_ciclo.data) > 0:
            ciclo_actual = respuesta_ciclo.data[0]
            valor_cupo = ciclo_actual["valor_nominal_cupo"]
            
            respuesta_cupos = supabase.table("cupos_miembros").select("*").eq("id_usuario", usuario['id']).eq("id_ciclo", ciclo_actual['id']).execute()
            
            if len(respuesta_cupos.data) > 0:
                mis_cupos = respuesta_cupos.data[0]["cantidad_cupos"]
                obligacion_mensual = mis_cupos * valor_cupo
                meta_anual = obligacion_mensual * 12
                
                respuesta_tx = supabase.table("transacciones").select("*").eq("id_usuario", usuario['id']).execute()
                aportes_aprobados = sum(tx["monto"] for tx in respuesta_tx.data if tx["tipo"] == "Aporte" and tx["estado"] == "Aprobado")
                aportes_pendientes = sum(tx["monto"] for tx in respuesta_tx.data if tx["tipo"] == "Aporte" and tx["estado"] == "Pendiente")
                saldo_restante = meta_anual - aportes_aprobados
                
                st.write(f"**Tu Plan de Ahorro 2026** | 🏷️ Valor base de un (1) cupo: **${valor_cupo:,.0f}**")
                col1, col2, col3 = st.columns(3)
                col1.metric("Cuota Mensual", f"${obligacion_mensual:,.0f}")
                col2.metric("Aportes Aprobados", f"${aportes_aprobados:,.0f}")
                col3.metric("Saldo Pendiente Anual", f"${saldo_restante:,.0f}")
                
                if aportes_pendientes > 0:
                    st.info(f"⏳ Registras **${aportes_pendientes:,.0f}** en estado 'Pendiente'.")
            else:
                st.warning("No tiene cupos asignados para este ciclo. Contacte al Administrador.")
        else:
            st.error("El año fiscal 2026 no ha sido configurado.")

    # --- PESTAÑA 1: REGISTRAR PAGO ---
    with tabs[1]:
        st.subheader("Subir comprobante de pago")
        meses = {"Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12}
        nombre_mes = st.selectbox("Mes de cobertura contable", list(meses.keys()), key="pago_mes")
        monto = st.number_input("Monto total transferido (COP)", min_value=0, step=10000, key="pago_monto")
        tipo = st.selectbox("Clasificación", ["Aporte", "Interes_Prestamo", "Actividad_Externa"], key="pago_tipo")
        archivo = st.file_uploader("Adjuntar Recibo (PNG, JPG, PDF)", type=['png', 'jpg', 'jpeg', 'pdf'], key="pago_archivo")
        
        if st.button("Enviar Transacción a Revisión", key="btn_enviar_pago"):
            if monto > 0 and archivo is not None:
                nombre_archivo_unico = f"usuario_{usuario['id']}_{datetime.datetime.now().timestamp()}_{archivo.name}"
                try:
                    supabase.storage.from_("comprobantes").upload(path=nombre_archivo_unico, file=archivo.getvalue(), file_options={"content-type": archivo.type})
                    url_publica = supabase.storage.from_("comprobantes").get_public_url(nombre_archivo_unico)
                    nuevo_pago = {"id_usuario": usuario['id'], "mes_correspondiente": meses[nombre_mes], "tipo": tipo, "monto": monto, "estado": "Pendiente", "url_comprobante": url_publica}
                    supabase.table("transacciones").insert(nuevo_pago).execute()
                    st.success("✅ Transacción grabada y archivo alojado.")
                    st.balloons()
                except Exception as e:
                    st.error(f"Fallo crítico en la carga: {e}")
            else:
                st.warning("⚠️ Formulario incompleto.")

    # --- PESTAÑA 2: HISTORIAL ---
    with tabs[2]:
        st.subheader("Historial Contable de Movimientos")
        respuesta_ledger = supabase.table("transacciones").select("*").eq("id_usuario", usuario['id']).order("id", desc=True).execute()
        if len(respuesta_ledger.data) > 0:
            st.dataframe(respuesta_ledger.data, use_container_width=True, column_config={"id": None, "id_usuario": None, "id_revisor": None, "url_comprobante": None})
        else:
            st.info("No registra movimientos históricos.")

    # --- PESTAÑA 3: PRÉSTAMOS ---
    with tabs[3]:
        st.subheader("🤝 Módulo de Colocación de Créditos")
        col_sol, col_vis = st.columns([1, 2])
        
        with col_sol:
            st.markdown("### Crear Solicitud")
            monto_p = st.number_input("Capital Solicitado (COP)", min_value=0, step=50000, key="prestamo_monto")
            tasa_p = st.number_input("Tasa Interés Mensual (%)", min_value=0.0, max_value=10.0, value=2.0, step=0.5, key="prestamo_tasa")
            fecha_lim = st.date_input("Fecha de Vencimiento", key="prestamo_fecha")
            
            if st.button("Radicar Solicitud", key="btn_radicar_prestamo"):
                if monto_p > 0:
                    data_prestamo = {"id_usuario": usuario['id'], "monto_solicitado": monto_p, "tasa_interes": tasa_p, "estado": "Solicitado", "fecha_limite": str(fecha_lim)}
                    supabase.table("prestamos").insert(data_prestamo).execute()
                    st.success("✅ Crédito radicado.")
                    st.rerun()
                else:
                    st.error("Monto inválido.")
                    
        with col_vis:
            st.markdown("### Tus Obligaciones")
            mis_p = supabase.table("prestamos").select("*").eq("id_usuario", usuario['id']).order("id", desc=True).execute()
            if len(mis_p.data) > 0:
                st.dataframe(mis_p.data, use_container_width=True, column_config={"id_usuario": None})
            else:
                st.info("No registra pasivos vigentes.")
                
            if es_revisor:
                st.write("---")
                st.markdown("### 🔑 Panel Evaluador (Rol Revisor)")
                p_pendientes = supabase.table("prestamos").select("*, usuarios(nombre)").eq("estado", "Solicitado").execute()
                if len(p_pendientes.data) > 0:
                    for p in p_pendientes.data:
                        nombre_solicitante = p['usuarios']['nombre'] if 'usuarios' in p else "Miembro"
                        with st.expander(f"Crédito ID {p['id']} - {nombre_solicitante} (${p['monto_solicitado']:,.0f})"):
                            st.write(f"Vencimiento: {p['fecha_limite']} | Tasa: {p['tasa_interes']}%")
                            cA, cB = st.columns(2)
                            if cA.button("✅ Conceder", key=f"ap_p_{p['id']}"):
                                supabase.table("prestamos").update({"estado": "Activo"}).eq("id", p['id']).execute()
                                st.rerun()
                            if cB.button("❌ Denegar", key=f"re_p_{p['id']}"):
                                supabase.table("prestamos").update({"estado": "Pagado"}).eq("id", p['id']).execute()
                                st.rerun()

    # --- PESTAÑA 4: CIERRE ANUAL (VISIÓN GERENCIAL Y PERSONAL) ---
    with tabs[4]:
        st.subheader("Cierre Contable y Distribución de Dividendos")
        
        # Leemos el ciclo actual (2026)
        resp_ciclo = supabase.table("configuracion_ciclo").select("id").eq("anio", 2026).execute()
        
        if len(resp_ciclo.data) > 0:
            id_ciclo_actual = resp_ciclo.data[0]['id']
            
            # 1. MATEMÁTICA BASE: GANANCIAS GLOBALES (Rendimientos a repartir)
            tx_rendimientos = supabase.table("transacciones").select("monto").in_("tipo", ["Interes_Prestamo", "Actividad_Externa"]).eq("estado", "Aprobado").execute()
            rendimientos_totales = sum(tx["monto"] for tx in tx_rendimientos.data)
            
            todos_cupos = supabase.table("cupos_miembros").select("cantidad_cupos").eq("id_ciclo", id_ciclo_actual).execute()
            total_cupos_vendidos = sum(c["cantidad_cupos"] for c in todos_cupos.data)
            
            rendimiento_por_cupo = (rendimientos_totales / total_cupos_vendidos) if total_cupos_vendidos > 0 else 0

            # ==================================================================
            # VISIÓN GERENCIAL (Exclusivo para Administrador y Tesorero)
            # ==================================================================
            if es_tesorero_admin:
                st.markdown("### 🌐 Panel de Control Global (Consolidado Familiar)")
                
                # Aportes totales puros de todo el fondo
                tx_aportes_global = supabase.table("transacciones").select("monto").eq("tipo", "Aporte").eq("estado", "Aprobado").execute()
                aportes_totales = sum(tx["monto"] for tx in tx_aportes_global.data)
                
                # Tarjetas de métricas globales
                colG1, colG2, colG3, colG4 = st.columns(4)
                colG1.metric("Caja Aportes Reales", f"${aportes_totales:,.0f}")
                colG2.metric("Utilidades (Rendimientos)", f"${rendimientos_totales:,.0f}")
                colG3.metric("Gran Total Consolidado", f"${(aportes_totales + rendimientos_totales):,.0f}")
                colG4.metric("Cupos Vendidos", f"{total_cupos_vendidos}")
                
                st.markdown("#### 👥 Libro Mayor de Liquidación por Ahorrador")
                
                # Extraemos y cruzamos los datos de todos los usuarios
                all_users = supabase.table("usuarios").select("id, nombre").eq("activo", True).execute()
                all_aportes = supabase.table("transacciones").select("id_usuario, monto").eq("tipo", "Aporte").eq("estado", "Aprobado").execute()
                all_cupos = supabase.table("cupos_miembros").select("id_usuario, cantidad_cupos").eq("id_ciclo", id_ciclo_actual).execute()
                
                detalle_ahorradores = []
                for u in all_users.data:
                    u_id = u['id']
                    # Sumamos los aportes y cupos individuales de forma dinámica
                    u_aportes = sum(tx['monto'] for tx in all_aportes.data if tx['id_usuario'] == u_id)
                    u_cupos = sum(c['cantidad_cupos'] for c in all_cupos.data if c['id_usuario'] == u_id)
                    
                    # Solo mostramos al usuario si tiene dinero o cupos activos
                    if u_cupos > 0 or u_aportes > 0:
                        u_ganancias = u_cupos * rendimiento_por_cupo
                        u_liquidacion = u_aportes + u_ganancias
                        detalle_ahorradores.append({
                            "Ahorrador": u['nombre'],
                            "Cupos": u_cupos,
                            "Ahorro Real": u_aportes,
                            "Utilidades": u_ganancias,
                            "Liquidación Total": u_liquidacion
                        })
                
                if len(detalle_ahorradores) > 0:
                    # Dibujamos la tabla con formato de moneda
                    st.dataframe(
                        detalle_ahorradores, 
                        use_container_width=True,
                        column_config={
                            "Ahorro Real": st.column_config.NumberColumn(format="$%d COP"),
                            "Utilidades": st.column_config.NumberColumn(format="$%d COP"),
                            "Liquidación Total": st.column_config.NumberColumn(format="$%d COP")
                        }
                    )
                else:
                    st.info("Aún no hay registros financieros para este ciclo.")
                    
                st.markdown("---")
                st.markdown("### 👤 Mi Cierre Personal")

            # ==================================================================
            # VISIÓN CLIENTE (Lo que ve cada Ahorrador para su propia cuenta)
            # ==================================================================
            mis_tx = supabase.table("transacciones").select("monto").eq("id_usuario", usuario['id']).eq("tipo", "Aporte").eq("estado", "Aprobado").execute()
            mi_ahorro_real = sum(tx["monto"] for tx in mis_tx.data)
            
            respuesta_mis_cupos = supabase.table("cupos_miembros").select("cantidad_cupos").eq("id_usuario", usuario['id']).eq("id_ciclo", id_ciclo_actual).execute()
            mis_cupos_liq = respuesta_mis_cupos.data[0]["cantidad_cupos"] if len(respuesta_mis_cupos.data) > 0 else 0
            
            mis_ganancias = mis_cupos_liq * rendimiento_por_cupo
            mi_liquidacion_total = mi_ahorro_real + mis_ganancias
            
            st.success(f"💰 Tu Liquidación Proyectada: **${mi_liquidacion_total:,.0f} COP**")
            
            colX, colY, colZ = st.columns(3)
            colX.metric("Tu Ahorro Real (Aportes)", f"${mi_ahorro_real:,.0f}")
            colY.metric("Tus Ganancias (Intereses/Rifas)", f"${mis_ganancias:,.0f}")
            colZ.metric("Rendimiento por 1 Cupo", f"${rendimiento_por_cupo:,.0f}")
            
            # El desglose global solo se lo mostramos al ahorrador común, 
            # ya que el Administrador/Tesorero ya tiene el gran panel gerencial arriba.
            if not es_tesorero_admin:
                with st.expander("📊 Ver desglose global del fondo (Auditoría)"):
                    st.write(f"**Utilidades totales del fondo a repartir:** ${rendimientos_totales:,.0f}")
                    st.write(f"**Total de cupos suscritos en la familia:** {total_cupos_vendidos}")
                    st.markdown("*Nota de negocio: El capital base no se prorratea. Recibes exactamente lo aportado de tu bolsillo, sumando las utilidades proporcionales a los cupos que contrataste.*")
        else:
            st.error("Configuración de ciclo no encontrada.")
            
    # ==========================================================================
    # PESTAÑAS ADMINISTRATIVAS CONDICIONALES
    # ==========================================================================
    idx_p = 5
    
    # --- PANEL REVISIÓN ---
    if es_revisor:
        with tabs[idx_p]:
            st.subheader("Auditoría de Pagos Pendientes")
            pagos_pendientes = supabase.table("transacciones").select("*").eq("estado", "Pendiente").execute()
            if len(pagos_pendientes.data) > 0:
                for tx in pagos_pendientes.data:
                    with st.expander(f"Transacción ID {tx['id']} - Monto: ${tx['monto']} - Mes: {tx['mes_correspondiente']}"):
                        st.markdown(f"**Soporte:** [Abrir Comprobante]({tx['url_comprobante']})")
                        colA, colB = st.columns(2)
                        if colA.button("✅ Aprobar", key=f"ap_{tx['id']}"):
                            supabase.table("transacciones").update({"estado": "Aprobado", "id_revisor": usuario['id']}).eq("id", tx['id']).execute()
                            st.rerun()
                        if colB.button("❌ Rechazar", key=f"re_{tx['id']}"):
                            supabase.table("transacciones").update({"estado": "Rechazado", "id_revisor": usuario['id']}).eq("id", tx['id']).execute()
                            st.rerun()
        idx_p += 1

    # --- PANEL GESTIÓN USUARIOS ---
    if es_admin:
        with tabs[idx_p]:
            st.subheader("👤 Registro Central de Miembros")
            col_u1, col_u2 = st.columns(2)
            with col_u1:
                st.markdown("### Nuevo Usuario")
                u_nombre = st.text_input("Nombre Completo", key="reg_nombre")
                u_correo = st.text_input("Correo electrónico", key="reg_correo").strip().lower()
                u_pass = st.text_input("Contraseña", type="password", key="reg_pass")
                u_rol = st.selectbox("Asignación de Privilegios", ["Ahorrador", "Revisor", "Tesorero", "Administrador", "Invitado"], key="reg_rol")
                
                if st.button("Ejecutar Alta de Usuario", key="btn_alta_usuario"):
                    if u_nombre and u_correo and u_pass:
                        try:
                            supabase.table("usuarios").insert({"nombre": u_nombre, "correo": u_correo, "contrasena_cifrada": u_pass, "rol": u_rol}).execute()
                            st.success(f"🎉 '{u_nombre}' registrado.")
                            st.rerun()
                        except Exception as error_u:
                            st.error(f"Error: {error_u}")
            
            with col_u2:
                st.markdown("### Directorio Actual")
                lista_usuarios = supabase.table("usuarios").select("id, nombre, correo, rol, activo").order("id", desc=False).execute()
                if len(lista_usuarios.data) > 0:
                    st.dataframe(lista_usuarios.data, use_container_width=True)

            st.markdown("---")
            st.markdown("### 🔒 Suspender / Activar Acceso de Usuarios")
            
            lista_us_bloqueo = supabase.table("usuarios").select("id, nombre, correo, activo").order("id", desc=False).execute()
            if len(lista_us_bloqueo.data) > 0:
                dicc_estado = {f"{u['nombre']} | {u['correo']} - {'🟢 Activo' if u.get('activo', True) else '🔴 Bloqueado'}": u for u in lista_us_bloqueo.data}
                
                col_b1, col_b2 = st.columns([1, 1])
                with col_b1:
                    sel_usuario_bloqueo = st.selectbox("Seleccionar Miembro", list(dicc_estado.keys()), key="sel_usuario_bloqueo")
                
                with col_b2:
                    st.write("") 
                    st.write("")
                    user_target = dicc_estado[sel_usuario_bloqueo]
                    estado_actual = user_target.get('activo', True)
                    
                    if estado_actual:
                        if st.button("🔴 Bloquear Acceso", key="btn_bloquear"):
                            if user_target['id'] == usuario['id']:
                                st.error("No puedes bloquear tu propia cuenta.")
                            else:
                                supabase.table("usuarios").update({"activo": False}).eq("id", user_target['id']).execute()
                                st.rerun()
                    else:
                        if st.button("🟢 Desbloquear Acceso", key="btn_desbloquear"):
                            supabase.table("usuarios").update({"activo": True}).eq("id", user_target['id']).execute()
                            st.rerun()
        idx_p += 1

    # --- PANEL ASIGNACIÓN DE CUPOS ---
    if es_tesorero_admin:
        with tabs[idx_p]:
            st.subheader("⚙️ Configuración de Cupos por Vigencia")
            
            lista_us = supabase.table("usuarios").select("id, nombre, correo").eq("activo", True).execute()
            lista_ci = supabase.table("configuracion_ciclo").select("id, anio").execute()
            
            if len(lista_us.data) > 0 and len(lista_ci.data) > 0:
                dicc_usuarios = {f"{u['nombre']} | {u['correo']}": u['id'] for u in lista_us.data}
                dicc_ciclos = {str(c['anio']): c['id'] for c in lista_ci.data}
                
                col_c1, col_c2 = st.columns([1, 1.5])
                with col_c1:
                    st.markdown("### Asignar Compromiso")
                    sel_user_name = st.selectbox("Seleccionar Usuario Activo", list(dicc_usuarios.keys()), key="cupo_usuario")
                    sel_ciclo_name = st.selectbox("Vigencia (Año)", list(dicc_ciclos.keys()), key="cupo_ciclo")
                    cant_cupos = st.number_input("Cantidad de Cupos Mensuales", min_value=1, step=1, key="cupo_cantidad")
                    
                    if st.button("Guardar Asignación", key="btn_guardar_cupos"):
                        id_u = dicc_usuarios[sel_user_name]
                        id_c = dicc_ciclos[sel_ciclo_name]
                        existe = supabase.table("cupos_miembros").select("id").eq("id_usuario", id_u).eq("id_ciclo", id_c).execute()
                        
                        try:
                            if len(existe.data) > 0:
                                supabase.table("cupos_miembros").update({"cantidad_cupos": cant_cupos}).eq("id", existe.data[0]['id']).execute()
                                st.success("Cupos actualizados.")
                            else:
                                supabase.table("cupos_miembros").insert({"id_usuario": id_u, "id_ciclo": id_c, "cantidad_cupos": cant_cupos}).execute()
                                st.success("Contrato creado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                
                with col_c2:
                    st.markdown("### Directorio Actual")
                    # CAMBIO APLICADO AQUÍ: Traemos el campo activo del usuario
                    cupos_actuales = supabase.table("cupos_miembros").select("cantidad_cupos, usuarios(nombre, activo), configuracion_ciclo(anio)").execute()
                    
                    if len(cupos_actuales.data) > 0:
                        datos_tabla = []
                        # Filtramos por Python: Solo mostramos los usuarios que siguen activos
                        for c in cupos_actuales.data:
                            if c['usuarios'] is not None and c['usuarios'].get('activo', True):
                                datos_tabla.append({
                                    "Usuario": c['usuarios']['nombre'], 
                                    "Año Vigencia": c['configuracion_ciclo']['anio'], 
                                    "Cupos": c['cantidad_cupos']
                                })
                        
                        if len(datos_tabla) > 0:
                            st.dataframe(datos_tabla, use_container_width=True)
                        else:
                            st.info("No hay cupos asignados a usuarios activos en este momento.")
                    else:
                        st.info("Aún no hay cupos asignados.")

# ==============================================================================
# 4. ENRUTADOR DE ACCESO
# ==============================================================================
if st.session_state['usuario_actual'] is None:
    pantalla_autenticacion()
else:
    pantalla_principal()