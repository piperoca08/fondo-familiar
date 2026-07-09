import streamlit as st
from supabase import create_client, Client
import datetime

# ==============================================================================
# 1. CONFIGURACIÓN DE NÚCLEO Y CONEXIÓN BÓVEDA DE DATOS (SUPABASE)
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
# 2. CAPA DE AUTENTICACIÓN (LOGIN CONTROL)
# ==============================================================================
def pantalla_autenticacion():
    st.title("🔐 Acceso al Sistema - Fondo Familiar")
    st.write("Bienvenido. Ingrese sus credenciales autorizadas.")
    
    col_login, _ = st.columns([1, 2])
    with col_login:
        correo = st.text_input("Correo electrónico").strip().lower()
        contrasena = st.text_input("Contraseña de seguridad", type="password")
        
        if st.button("Iniciar Sesión"):
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
# 3. CAPA DE APLICACIÓN - PANEL INTERNO PRINCIPAL (DASHBOARD COMPLETO)
# ==============================================================================
def pantalla_principal():
    usuario = st.session_state['usuario_actual']
    
    st.sidebar.title(f"Hola, {usuario['nombre']} 👋")
    st.sidebar.info(f"**Rol:** {usuario['rol']}")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['usuario_actual'] = None 
        st.rerun()
        
    st.title("📊 Sistema Integral de Gestión Financiera")
    
    es_admin = usuario['rol'] == "Administrador"
    es_revisor = usuario['rol'] in ["Administrador", "Revisor", "Tesorero"]
    
    nombres_pestanas = ["Resumen", "💸 Pagar", "📜 Historial", "🤝 Préstamos", "📅 Cierre Anual"]
    if es_revisor:
        nombres_pestanas.append("✅ Revisión Pagos")
    if es_admin:
        nombres_pestanas.append("👤 Gestión Usuarios")
        
    tabs = st.tabs(nombres_pestanas)
    
    # --------------------------------------------------------------------------
    # PESTAÑA 0: RESUMEN FINANCIERO DINÁMICO
    # --------------------------------------------------------------------------
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
                st.warning("No tiene cupos asignados para este ciclo.")
        else:
            st.error("El año fiscal 2026 no ha sido configurado.")

    # --------------------------------------------------------------------------
    # PESTAÑA 1: REGISTRO TRANSACCIONAL (WRITE AND UPLOAD)
    # --------------------------------------------------------------------------
    with tabs[1]:
        st.subheader("Subir comprobante de pago")
        meses = {"Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12}
        nombre_mes = st.selectbox("Mes de cobertura contable", list(meses.keys()))
        monto = st.number_input("Monto total transferido (COP)", min_value=0, step=10000, key="pago_monto")
        tipo = st.selectbox("Clasificación del Movimiento", ["Aporte", "Interes_Prestamo", "Actividad_Externa"])
        archivo = st.file_uploader("Adjuntar Recibo (PNG, JPG, PDF)", type=['png', 'jpg', 'jpeg', 'pdf'])
        
        if st.button("Enviar Transacción a Revisión"):
            if monto > 0 and archivo is not None:
                nombre_archivo_unico = f"usuario_{usuario['id']}_{datetime.datetime.now().timestamp()}_{archivo.name}"
                try:
                    supabase.storage.from_("comprobantes").upload(path=nombre_archivo_unico, file=archivo.getvalue(), file_options={"content-type": archivo.type})
                    url_publica = supabase.storage.from_("comprobantes").get_public_url(nombre_archivo_unico)
                    nuevo_pago = {"id_usuario": usuario['id'], "mes_correspondiente": meses[nombre_mes], "tipo": tipo, "monto": monto, "estado": "Pendiente", "url_comprobante": url_publica}
                    supabase.table("transacciones").insert(nuevo_pago).execute()
                    st.success("✅ Transacción grabada y archivo alojado en la bóveda correctamente.")
                    st.balloons()
                except Exception as e:
                    st.error(f"Fallo crítico en la carga: {e}")
            else:
                st.warning("⚠️ Formulario incompleto. Diligencie el monto y cargue el soporte físico.")

    # --------------------------------------------------------------------------
    # PESTAÑA 2: VISUALIZACIÓN INDIVIDUAL DEL LEDGER
    # --------------------------------------------------------------------------
    with tabs[2]:
        st.subheader("Historial Contable de Movimientos")
        respuesta_ledger = supabase.table("transacciones").select("*").eq("id_usuario", usuario['id']).order("id", desc=True).execute()
        if len(respuesta_ledger.data) > 0:
            st.dataframe(respuesta_ledger.data, use_container_width=True, column_config={"id": None, "id_usuario": None, "id_revisor": None, "url_comprobante": None})
        else:
            st.info("No registra movimientos históricos en el Libro Mayor.")

    # --------------------------------------------------------------------------
    # PESTAÑA 3: MODULO COMPLETO DE CRÉDITOS Y PRÉSTAMOS
    # --------------------------------------------------------------------------
    with tabs[3]:
        st.subheader("🤝 Módulo de Colocación de Créditos Familiares")
        col_sol, col_vis = st.columns([1, 2])
        
        with col_sol:
            st.markdown("### Crear Solicitud de Préstamo")
            monto_p = st.number_input("Capital Solicitado (COP)", min_value=0, step=50000, key="monto_p")
            tasa_p = st.number_input("Tasa Interés Mensual Nominal (%)", min_value=0.0, max_value=10.0, value=2.0, step=0.5)
            fecha_lim = st.date_input("Fecha de Vencimiento de Obligación")
            
            if monto_p > 0:
                interes_estimado = monto_p * (tasa_p / 100)
                st.warning(f"📊 **Simulación Contable:** Interés Mensual: ${interes_estimado:,.0f} | Retorno Total: ${(monto_p + interes_estimado):,.0f}")
                
            if st.button("Radicar Solicitud de Crédito"):
                if monto_p > 0:
                    data_prestamo = {"id_usuario": usuario['id'], "monto_solicitado": monto_p, "tasa_interes": tasa_p, "estado": "Solicitado", "fecha_limite": str(fecha_lim)}
                    supabase.table("prestamos").insert(data_prestamo).execute()
                    st.success("✅ Crédito radicado. Pendiente de evaluación por el comité.")
                    st.rerun()
                else:
                    st.error("Monto de capital inválido.")
                    
        with col_vis:
            st.markdown("### Estado de tus Obligaciones Crediticias")
            mis_p = supabase.table("prestamos").select("*").eq("id_usuario", usuario['id']).order("id", desc=True).execute()
            if len(mis_p.data) > 0:
                st.dataframe(mis_p.data, use_container_width=True, column_config={"id_usuario": None})
            else:
                st.info("No registra pasivos vigentes ni solicitudes en curso.")
                
            if es_revisor:
                st.write("---")
                st.markdown("### 🔑 Panel Evaluador de Créditos (Rol Revisor)")
                p_pendientes = supabase.table("prestamos").select("*, usuarios(nombre)").eq("estado", "Solicitado").execute()
                
                if len(p_pendientes.data) > 0:
                    for p in p_pendientes.data:
                        nombre_solicitante = p['usuarios']['nombre'] if 'usuarios' in p else "Miembro Fondo"
                        with st.expander(f"Crédito ID {p['id']} - {nombre_solicitante} (${p['monto_solicitado']:,.0f})"):
                            st.write(f"Vencimiento: {p['fecha_limite']} | Tasa mensual pactada: {p['tasa_interes']}%")
                            cA, cB = st.columns(2)
                            if cA.button("✅ Conceder y Activar", key=f"ap_p_{p['id']}"):
                                supabase.table("prestamos").update({"estado": "Activo"}).eq("id", p['id']).execute()
                                st.rerun()
                            if cB.button("❌ Denegar Crédito", key=f"re_p_{p['id']}"):
                                supabase.table("prestamos").update({"estado": "Pagado"}).eq("id", p['id']).execute()
                                st.rerun()
                else:
                    st.success("No existen créditos en cola de evaluación.")

    # --------------------------------------------------------------------------
    # PESTAÑA 4: PROYECCIÓN DINÁMICA DE LIQUIDACIÓN ANUAL
    # --------------------------------------------------------------------------
    with tabs[4]:
        st.subheader("Cierre Contable y Distribución de Dividendos")
        todas_tx = supabase.table("transacciones").select("monto").eq("estado", "Aprobado").execute()
        fondo_total = sum(tx["monto"] for tx in todas_tx.data)
        
        todos_cupos = supabase.table("cupos_miembros").select("cantidad_cupos").eq("id_ciclo", 1).execute()
        total_cupos_vendidos = sum(c["cantidad_cupos"] for c in todos_cupos.data)
        
        if total_cupos_vendidos > 0:
            valor_final_cupo = fondo_total / total_cupos_vendidos
            respuesta_mis_cupos = supabase.table("cupos_miembros").select("cantidad_cupos").eq("id_usuario", usuario['id']).eq("id_ciclo", 1).execute()
            mis_cupos_liq = respuesta_mis_cupos.data[0]["cantidad_cupos"] if len(respuesta_mis_cupos.data) > 0 else 0
            mi_liquidacion = mis_cupos_liq * valor_final_cupo
            
            st.success(f"💰 Balance Consolidado Líquido del Fondo: **${fondo_total:,.0f} COP**")
            colX, colY = st.columns(2)
            colX.metric("Valor Neto Actualizado por Cupo", f"${valor_final_cupo:,.0f}")
            colY.metric("Tu Retorno Proyectado", f"${mi_liquidacion:,.0f}")
        else:
            st.warning("Datos insuficientes en el modelo relacional para computar la liquidación.")

    # --------------------------------------------------------------------------
    # PESTAÑA 5: PANEL AUDITOR DE TRANSACCIONES (REVISORES / TESOREROS)
    # --------------------------------------------------------------------------
    idx_p = 5
    if es_revisor:
        with tabs[idx_p]:
            st.subheader("Auditoría de Pagos Pendientes de Aprobación")
            pagos_pendientes = supabase.table("transacciones").select("*").eq("estado", "Pendiente").execute()
            if len(pagos_pendientes.data) > 0:
                for tx in pagos_pendientes.data:
                    with st.expander(f"Transacción ID {tx['id']} - Monto: ${tx['monto']} - Mes contable: {tx['mes_correspondiente']}"):
                        st.markdown(f"**Soporte Técnico:** [Abrir Comprobante Original]({tx['url_comprobante']})")
                        colA, colB = st.columns(2)
                        if colA.button("✅ Conciliar y Aprobar", key=f"ap_{tx['id']}"):
                            supabase.table("transacciones").update({"estado": "Aprobado", "id_revisor": usuario['id']}).eq("id", tx['id']).execute()
                            st.rerun()
                        if colB.button("❌ Rechazar Transacción", key=f"re_{tx['id']}"):
                            supabase.table("transacciones").update({"estado": "Rechazado", "id_revisor": usuario['id']}).eq("id", tx['id']).execute()
                            st.rerun()
            else:
                st.success("No se registran transacciones pendientes. Libro Mayor conciliado.")
        idx_p += 1

    # --------------------------------------------------------------------------
    # PESTAÑA 6: CONTROL DE MIEMBROS Y ASIGNACIÓN DE ROLES (ADMINISTRADOR)
    # --------------------------------------------------------------------------
    if es_admin:
        with tabs[idx_p]:
            st.subheader("👤 Registro Central de Miembros y Concesión de Roles")
            col_u1, col_u2 = st.columns(2)
            
            with col_u1:
                st.markdown("### Dar de Alta Nuevo Miembro")
                u_nombre = st.text_input("Nombre Completo y Apellidos")
                u_correo = st.text_input("Identificador / Correo electrónico").strip().lower()
                u_pass = st.text_input("Contraseña Temporal de Acceso", type="password")
                u_rol = st.selectbox("Asignación de Privilegios Operativos", ["Ahorrador", "Revisor", "Tesorero", "Administrador", "Invitado"])
                
                if st.button("Ejecutar Alta de Usuario"):
                    if u_nombre and u_correo and u_pass:
                        nuevo_user = {"nombre": u_nombre, "correo": u_correo, "contrasena_cifrada": u_pass, "rol": u_rol}
                        try:
                            supabase.table("usuarios").insert(nuevo_user).execute()
                            st.success(f"🎉 El usuario '{u_nombre}' ha sido mapeado exitosamente con rol '{u_rol}'.")
                            st.rerun()
                        except Exception as error_u:
                            st.error(f"Fallo en la restricción de unicidad: {error_u}")
                    else:
                        st.error("Todos los campos relacionales del formulario son obligatorios.")
                        
            with col_u2:
                st.markdown("### Directorio y Gafetes Operativos de Miembros")
                lista_usuarios = supabase.table("usuarios").select("id, nombre, correo, rol").order("id", desc=False).execute()
                if len(lista_usuarios.data) > 0:
                    st.dataframe(lista_usuarios.data, use_container_width=True)

# ==============================================================================
# 4. ENRUTADOR INICIAL DE CONTROL DE FLUJO
# ==============================================================================
if st.session_state['usuario_actual'] is None:
    pantalla_autenticacion()
else:
    pantalla_principal()