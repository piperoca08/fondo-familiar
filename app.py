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
                    st.session_state['usuario_actual'] = usuario_db
                    st.success(f"Ingreso autorizado para {usuario_db['nombre']}.")
                    st.rerun()
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
    
    # Banderas de Seguridad por Rol
    es_admin = usuario['rol'] == "Administrador"
    es_revisor = usuario['rol'] in ["Administrador", "Revisor", "Tesorero"]
    es_tesorero_admin = usuario['rol'] in ["Administrador", "Tesorero"]
    
    # Generador Dinámico de Pestañas
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
                    st.info(f"⏳ Registras **${aportes_pendientes:,.0f}** en estado 'Pendiente' de aprobación.")
            else:
                st.warning("No tiene cupos asignados para este ciclo. Contacte al Administrador o Tesorero.")
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
            
            if monto_p > 0:
                interes_estimado = monto_p * (tasa_p / 100)
                st.warning(f"📊 Interés Mensual: ${interes_estimado:,.0f} | Retorno Total: ${(monto_p + interes_estimado):,.0f}")
                
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
                else:
                    st.success("No existen créditos en cola.")

    # --- PESTAÑA 4: CIERRE ANUAL ---
    with tabs[4]:
        st.subheader("Cierre Contable y Distribución de Dividendos")
        resp_ciclo = supabase.table("configuracion_ciclo").select("id").eq("anio", 2026).execute()
        
        if len(resp_ciclo.data) > 0:
            id_ciclo_actual = resp_ciclo.data[0]['id']
            todas_tx = supabase.table("transacciones").select("monto").eq("estado", "Aprobado").execute()
            fondo_total = sum(tx["monto"] for tx in todas_tx.data)
            
            todos_cupos = supabase.table("cupos_miembros").select("cantidad_cupos").eq("id_ciclo", id_ciclo_actual).execute()
            total_cupos_vendidos = sum(c["cantidad_cupos"] for c in todos_cupos.data)
            
            if total_cupos_vendidos > 0:
                valor_final_cupo = fondo_total / total_cupos_vendidos
                respuesta_mis_cupos = supabase.table("cupos_miembros").select("cantidad_cupos").eq("id_usuario", usuario['id']).eq("id_ciclo", id_ciclo_actual).execute()
                mis_cupos_liq = respuesta_mis_cupos.data[0]["cantidad_cupos"] if len(respuesta_mis_cupos.data) > 0 else 0
                mi_liquidacion = mis_cupos_liq * valor_final_cupo
                
                st.success(f"💰 Balance Consolidado Líquido: **${fondo_total:,.0f} COP**")
                colX, colY = st.columns(2)
                colX.metric("Valor Neto por Cupo", f"${valor_final_cupo:,.0f}")
                colY.metric("Tu Retorno Proyectado", f"${mi_liquidacion:,.0f}")
            else:
                st.warning("No hay cupos asignados en el sistema.")
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
            else:
                st.success("No se registran transacciones pendientes.")
        idx_p += 1

    # --- PANEL GESTIÓN USUARIOS ---
    if es_admin:
        with tabs[idx_p]:
            st.subheader("👤 Registro Central de Miembros")
            col_u1, col_u2 = st.columns(2)
            with col_u1:
                u_nombre = st.text_input("Nombre Completo", key="reg_nombre")
                u_correo = st.text_input("Correo electrónico", key="reg_correo").strip().lower()
                u_pass = st.text_input("Contraseña", type="password", key="reg_pass")
                u_rol = st.selectbox("Asignación de Privilegios", ["Ahorrador", "Revisor", "Tesorero", "Administrador", "Invitado"], key="reg_rol")
                
                if st.button("Ejecutar Alta de Usuario", key="btn_alta_usuario"):
                    if u_nombre and u_correo and u_pass:
                        try:
                            supabase.table("usuarios").insert({"nombre": u_nombre, "correo": u_correo, "contrasena_cifrada": u_pass, "rol": u_rol}).execute()
                            st.success(f"🎉 '{u_nombre}' registrado con rol '{u_rol}'.")
                            st.rerun()
                        except Exception as error_u:
                            st.error(f"Error: {error_u}")
                    else:
                        st.error("Campos obligatorios.")
            with col_u2:
                lista_usuarios = supabase.table("usuarios").select("id, nombre, correo, rol").order("id", desc=False).execute()
                if len(lista_usuarios.data) > 0:
                    st.dataframe(lista_usuarios.data, use_container_width=True)
        idx_p += 1

    # --- PANEL ASIGNACIÓN DE CUPOS ---
    if es_tesorero_admin:
        with tabs[idx_p]:
            st.subheader("⚙️ Configuración de Cupos por Vigencia")
            st.write("Asigna o modifica la cantidad de cupos comprometidos por cada miembro según el año fiscal.")
            
            lista_us = supabase.table("usuarios").select("id, nombre, rol").execute()
            lista_ci = supabase.table("configuracion_ciclo").select("id, anio").execute()
            
            if len(lista_us.data) > 0 and len(lista_ci.data) > 0:
                dicc_usuarios = {f"{u['nombre']} ({u['rol']})": u['id'] for u in lista_us.data}
                dicc_ciclos = {str(c['anio']): c['id'] for c in lista_ci.data}
                
                col_c1, col_c2 = st.columns([1, 1.5])
                with col_c1:
                    st.markdown("### Asignar Compromiso")
                    sel_user_name = st.selectbox("Seleccionar Usuario", list(dicc_usuarios.keys()), key="cupo_usuario")
                    sel_ciclo_name = st.selectbox("Vigencia (Año)", list(dicc_ciclos.keys()), key="cupo_ciclo")
                    cant_cupos = st.number_input("Cantidad de Cupos Mensuales", min_value=1, step=1, key="cupo_cantidad")
                    
                    if st.button("Guardar Asignación de Cupos", key="btn_guardar_cupos"):
                        id_u = dicc_usuarios[sel_user_name]
                        id_c = dicc_ciclos[sel_ciclo_name]
                        existe = supabase.table("cupos_miembros").select("id").eq("id_usuario", id_u).eq("id_ciclo", id_c).execute()
                        
                        try:
                            if len(existe.data) > 0:
                                id_registro = existe.data[0]['id']
                                supabase.table("cupos_miembros").update({"cantidad_cupos": cant_cupos}).eq("id", id_registro).execute()
                                st.success("Cupos actualizados correctamente.")
                            else:
                                supabase.table("cupos_miembros").insert({"id_usuario": id_u, "id_ciclo": id_c, "cantidad_cupos": cant_cupos}).execute()
                                st.success("Contrato creado correctamente.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                
                with col_c2:
                    st.markdown("### Directorio Actual")
                    cupos_actuales = supabase.table("cupos_miembros").select("cantidad_cupos, usuarios(nombre), configuracion_ciclo(anio)").execute()
                    if len(cupos_actuales.data) > 0:
                        datos_tabla = [{"Usuario": c['usuarios']['nombre'], "Año Vigencia": c['configuracion_ciclo']['anio'], "Cupos Contratados": c['cantidad_cupos']} for c in cupos_actuales.data]
                        st.dataframe(datos_tabla, use_container_width=True)
                    else:
                        st.info("Aún no hay cupos asignados.")
            else:
                st.warning("Debe existir al menos un usuario y un ciclo configurado.")

# ==============================================================================
# 4. ENRUTADOR DE ACCESO
# ==============================================================================
if st.session_state['usuario_actual'] is None:
    pantalla_autenticacion()
else:
    pantalla_principal()