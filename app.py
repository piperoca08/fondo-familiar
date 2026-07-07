import streamlit as st
from supabase import create_client, Client

# 1. Configuración visual básica
st.set_page_config(page_title="Fondo Familiar", page_icon="💰", layout="centered")

# 2. Conexión a la bóveda (Supabase)
@st.cache_resource
def iniciar_conexion():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = iniciar_conexion()

# 3. El "Gafete de Visitante" (Sistema de memoria de la sesión)
if 'usuario_actual' not in st.session_state:
    st.session_state['usuario_actual'] = None

# 4. Pantalla de Puerta de Entrada (Login)
def pantalla_login():
    st.title("🔐 Acceso al Fondo Familiar")
    st.write("Por favor, ingresa tus credenciales.")
    
    correo = st.text_input("Correo electrónico").strip().lower()
    contrasena = st.text_input("Contraseña", type="password") # type="password" oculta el texto
    
    if st.button("Ingresar"):
        # Le decimos al mensajero que busque en la tabla usuarios si el correo existe
        respuesta = supabase.table("usuarios").select("*").eq("correo", correo).execute()
        datos = respuesta.data
        
        if len(datos) > 0:
            usuario_encontrado = datos[0]
            # Verificamos que la contraseña coincida
            if usuario_encontrado["contrasena_cifrada"] == contrasena:
                # ¡Éxito! Le entregamos el gafete
                st.session_state['usuario_actual'] = usuario_encontrado
                st.success("Acceso concedido. Cargando...")
                st.rerun() # Esto recarga la página rápidamente para mostrar el menú
            else:
                st.error("Contraseña incorrecta.")
        else:
            st.error("No existe ningún usuario con este correo.")

# 5. Pantalla Interna (Lo que ven cuando ya entraron)
def pantalla_principal():
    usuario = st.session_state['usuario_actual']
    
    st.sidebar.title(f"Hola, {usuario['nombre']} 👋")
    st.sidebar.info(f"**Rol:** {usuario['rol']}")
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['usuario_actual'] = None 
        st.rerun()
        
    st.title("📊 Panel de Control")
    
    es_auditor = usuario['rol'] in ["Administrador", "Revisor"]
    
    # Agregamos la pestaña "Cierre Anual"
    nombres_pestanas = ["Resumen", "💸 Pagar", "📜 Historial", "📅 Cierre Anual"]
    if es_auditor:
        nombres_pestanas.append("✅ Revisión")
        
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
                
                st.write(f"🏷️ Valor base de un (1) cupo: **${valor_cupo:,.0f}**")
                col1, col2, col3 = st.columns(3)
                col1.metric("Cuota Mensual", f"${obligacion_mensual:,.0f}")
                col2.metric("Aportes Aprobados", f"${aportes_aprobados:,.0f}")
                col3.metric("Saldo Pendiente", f"${saldo_restante:,.0f}")
                
                if aportes_pendientes > 0:
                    st.info(f"⏳ Tienes **${aportes_pendientes:,.0f}** en estado 'Pendiente'.")
            else:
                st.warning("Aún no tienes cupos asignados para este año.")
        else:
            st.error("No se ha configurado el año 2026.")

    # --- PESTAÑA 1: REGISTRAR PAGO ---
    with tabs[1]:
        st.subheader("Subir comprobante de pago")
        meses = {"Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12}
        nombre_mes = st.selectbox("¿Qué mes estás pagando?", list(meses.keys()))
        monto = st.number_input("Monto del pago (COP)", min_value=0, step=10000)
        tipo = st.selectbox("¿A qué corresponde este pago?", ["Aporte", "Interes_Prestamo", "Actividad_Externa"])
        archivo = st.file_uploader("Sube la foto o PDF del recibo", type=['png', 'jpg', 'jpeg', 'pdf'])
        
        if st.button("Enviar a Revisión"):
            if monto > 0 and archivo is not None:
                nombre_archivo_unico = f"usuario_{usuario['id']}_{archivo.name}"
                try:
                    supabase.storage.from_("comprobantes").upload(path=nombre_archivo_unico, file=archivo.getvalue(), file_options={"content-type": archivo.type})
                    url_publica = supabase.storage.from_("comprobantes").get_public_url(nombre_archivo_unico)
                    nuevo_pago = {"id_usuario": usuario['id'], "mes_correspondiente": meses[nombre_mes], "tipo": tipo, "monto": monto, "estado": "Pendiente", "url_comprobante": url_publica}
                    supabase.table("transacciones").insert(nuevo_pago).execute()
                    st.success("✅ ¡Pago registrado!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("⚠️ Completa el monto y sube una foto.")

    # --- PESTAÑA 2: HISTORIAL ---
    with tabs[2]:
        st.subheader("Tus movimientos (Ledger)")
        respuesta_ledger = supabase.table("transacciones").select("*").eq("id_usuario", usuario['id']).order("id", desc=True).execute()
        if len(respuesta_ledger.data) > 0:
            st.dataframe(respuesta_ledger.data, use_container_width=True, column_config={"id": None, "id_usuario": None, "id_revisor": None, "url_comprobante": None})
        else:
            st.info("Aún no tienes movimientos registrados.")

    # --- PESTAÑA 3: CIERRE ANUAL (LIQUIDACIÓN) ---
    with tabs[3]:
        st.subheader("Proyección Final de Fin de Año")
        st.write("Esta matemática audita todo el libro mayor y calcula el crecimiento de tus cupos.")
        
        # 1. Traemos TODAS las transacciones aprobadas de TODO el fondo
        todas_tx = supabase.table("transacciones").select("monto").eq("estado", "Aprobado").execute()
        fondo_total = sum(tx["monto"] for tx in todas_tx.data)
        
        # 2. Traemos TODOS los cupos vendidos (del ciclo activo 1)
        todos_cupos = supabase.table("cupos_miembros").select("cantidad_cupos").eq("id_ciclo", 1).execute()
        total_cupos_vendidos = sum(c["cantidad_cupos"] for c in todos_cupos.data)
        
        # 3. Matemática de liquidación
        if total_cupos_vendidos > 0:
            valor_final_cupo = fondo_total / total_cupos_vendidos
            
            # Buscamos los cupos del usuario actual
            respuesta_mis_cupos = supabase.table("cupos_miembros").select("cantidad_cupos").eq("id_usuario", usuario['id']).eq("id_ciclo", 1).execute()
            mis_cupos_liq = respuesta_mis_cupos.data[0]["cantidad_cupos"] if len(respuesta_mis_cupos.data) > 0 else 0
            
            mi_liquidacion = mis_cupos_liq * valor_final_cupo
            
            st.success(f"💰 El tamaño total del fondo en este momento es de **${fondo_total:,.0f} COP**")
            
            colX, colY = st.columns(2)
            colX.metric("Valor Actualizado por Cupo", f"${valor_final_cupo:,.0f}")
            colY.metric("Tu Liquidación Estimada", f"${mi_liquidacion:,.0f}")
            
            st.info("Nota: Este valor crecerá si se inyectan intereses de préstamos o actividades externas.")
        else:
            st.warning("No hay datos suficientes para calcular la liquidación.")

    # --- PESTAÑA 4: PANEL DE REVISIÓN (Auditores) ---
    if es_auditor:
        with tabs[4]:
            st.subheader("Auditoría de Pagos Pendientes")
            pagos_pendientes = supabase.table("transacciones").select("*").eq("estado", "Pendiente").execute()
            
            if len(pagos_pendientes.data) > 0:
                for tx in pagos_pendientes.data:
                    with st.expander(f"💰 Pago de ${tx['monto']} (Mes: {tx['mes_correspondiente']})"):
                        st.markdown(f"**Comprobante:** [Ver foto]({tx['url_comprobante']})")
                        colA, colB = st.columns(2)
                        if colA.button("✅ Aprobar", key=f"ap_{tx['id']}"):
                            supabase.table("transacciones").update({"estado": "Aprobado", "id_revisor": usuario['id']}).eq("id", tx['id']).execute()
                            st.rerun()
                        if colB.button("❌ Rechazar", key=f"re_{tx['id']}"):
                            supabase.table("transacciones").update({"estado": "Rechazado", "id_revisor": usuario['id']}).eq("id", tx['id']).execute()
                            st.rerun()
            else:
                st.success("Todo está al día.")
                               
# 6. Lógica de control de tráfico (Quién ve qué)
if st.session_state['usuario_actual'] is None:
    pantalla_login()
else:
    pantalla_principal()