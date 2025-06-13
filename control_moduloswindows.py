#!/usr/bin/env python3
"""
control_modulos.py

Panel gráfico para administrar módulos y servidores por SSH, ahora con menú "Servidores"
para reiniciar o apagar hosts, sin pedir contraseña.
"""

import paramiko
import threading
import time
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import re

HOSTS_RECEPTORES = ["10.2.12.30", "10.2.12.31", "10.2.12.32"]
HOSTS_PASEADORES = ["10.2.12.41", "10.2.12.42"]
USERNAME = "stopcar"
PASSWORD = "Mitesia635$!"
SCRIPT_PATH = "/home/stopcar/modulos.py"
UPDATE_SCRIPT_PATH = "/home/stopcar/actualizargit.py"
SSH_PORT = 22
SERVICES_POR_HOST = {
    "10.2.12.30": ["7001-7010.service", "7011-7020.service"],
    "10.2.12.31": ["7021-7049.service"],
    "10.2.12.32": ["7050-7080.service", "7100.service"],
    "10.2.12.41": ["7100.service", "7001-7010.service", "7011-7021.service", "7022-7031.service", "7032-7045.service"],
    "10.2.12.42": ["7021-7049.service", "7050-7080.service"]
}
OPTIONS = {"Iniciar módulos": "1", "Detener módulos": "2", "Reiniciar módulos": "3"}

def append_log_color(texto: str, log_area: ScrolledText, tag: str = None):
    if not texto.endswith("\n"):
        texto += "\n"
    def inner():
        log_area.configure(state="normal")
        if tag is None:
            log_area.insert(tk.END, texto)
        else:
            log_area.insert(tk.END, texto, tag)
        log_area.see(tk.END)
        log_area.configure(state="disabled")
    log_area.after(0, inner)

# Terminal embebida (solo directorios azules)
def open_terminal_embedded(host):
    term = tk.Toplevel()
    term.title(f"Terminal SSH - {host}")
    term.geometry("900x500")
    txt = ScrolledText(term, wrap="word", font=("Menlo", 13))
    txt.pack(fill="both", expand=True)
    entry = tk.Entry(term, font=("Menlo", 13))
    entry.pack(fill="x")
    entry.focus_set()
    txt.tag_configure("blue", foreground="blue")
    def insert_ansi_only_blue(txt_widget, text):
        ANSI_REGEX = re.compile(r'\x1b\[(?P<code>\d+(;\d+)*)m')
        tag = None
        last_end = 0
        for m in ANSI_REGEX.finditer(text):
            if m.start() > last_end:
                segment = text[last_end:m.start()]
                txt_widget.insert(tk.END, segment, tag)
            code_str = m.group('code')
            codes = code_str.split(';')
            if '0' in codes:
                tag = None
            elif '34' in codes:
                tag = 'blue'
            else:
                tag = None
            last_end = m.end()
        if last_end < len(text):
            txt_widget.insert(tk.END, text[last_end:], tag)
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port=SSH_PORT, username=USERNAME, password=PASSWORD, timeout=10)
        chan = client.invoke_shell()
    except Exception as e:
        txt.insert(tk.END, f"Error al conectar: {e}\n")
        return
    stop_reader = threading.Event()
    def reader():
        while not stop_reader.is_set():
            try:
                if chan.recv_ready():
                    data = chan.recv(4096).decode(errors="ignore")
                    insert_ansi_only_blue(txt, data)
                    txt.see(tk.END)
                else:
                    time.sleep(0.05)
            except Exception:
                break
    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    def send_cmd(event):
        cmd = entry.get().strip()
        if cmd == "clear":
            txt.delete("1.0", tk.END)
            entry.delete(0, tk.END)
            return
        if chan.closed:
            txt.insert(tk.END, "\n[Canal SSH cerrado]\n")
            return
        chan.send(cmd + "\n")
        entry.delete(0, tk.END)
    entry.bind("<Return>", send_cmd)
    def cerrar_terminal():
        stop_reader.set()
        try:
            chan.close()
            client.close()
        except:
            pass
        term.destroy()
    term.protocol("WM_DELETE_WINDOW", cerrar_terminal)

def ejecutar_en_servidor(host: str, opcion: str, log_callback):
    log_callback(f"[{host}] → Iniciando conexión SSH...", None)
    try:
        cliente = paramiko.SSHClient()
        cliente.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        cliente.connect(
            hostname=host,
            port=SSH_PORT,
            username=USERNAME,
            password=PASSWORD,
            timeout=10
        )
        comando = f"sudo -S python3 {SCRIPT_PATH}"
        stdin, stdout, stderr = cliente.exec_command(comando, get_pty=True)
        stdin.write(PASSWORD + "\n")
        stdin.flush()
        time.sleep(0.5)
        stdin.write(opcion + "\n")
        stdin.flush()
        time.sleep(0.5)
        stdin.write("5\n")
        stdin.flush()
        for line in stdout:
            line = line.rstrip("\n")
            if line:
                log_callback(f"[{host}] → STDOUT: {line}", None)
        for line in stderr:
            line = line.rstrip("\n")
            if line:
                log_callback(f"[{host}] → STDERR: {line}", None)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            log_callback(f"[{host}] → Acción completada con éxito (exit code = 0).", "success")
        else:
            log_callback(f"[{host}] → Error al ejecutar la acción (exit code = {exit_status}).", "error")
        cliente.close()
        log_callback(f"[{host}] → Conexión finalizada.\n", None)
    except Exception as e:
        log_callback(f"[{host}] → EXCEPCIÓN: {e}\n", "error")

def ejecutar_para_hosts(hosts: list, opcion: str, log_area: ScrolledText, bloque_nombre: str):
    def tarea():
        log_area.configure(state="normal")
        log_area.delete("1.0", tk.END)
        log_area.insert(tk.END, f"==== [{bloque_nombre}] Acción '{opcion}' en los hosts ====\n\n")
        log_area.configure(state="disabled")
        for h in hosts:
            ejecutar_en_servidor(
                host=h,
                opcion=opcion,
                log_callback=lambda texto, tag=None: append_log_color(texto, log_area, tag)
            )
            time.sleep(0.5)
        append_log_color(f"==== [{bloque_nombre}] Todas las acciones completadas ====\n", log_area, None)
    threading.Thread(target=tarea, daemon=True).start()

def verificar_estado_bloque(hosts: list, log_area: ScrolledText, bloque_nombre: str):
    def tarea_estado():
        log_area.configure(state="normal")
        log_area.delete("1.0", tk.END)
        log_area.insert(tk.END, f"==== [{bloque_nombre}] Verificando estado de servicios ====\n\n")
        log_area.configure(state="disabled")
        for host in hosts:
            servicios = SERVICES_POR_HOST.get(host, [])
            if not servicios:
                append_log_color(f"[{host}] → No hay servicios definidos en SERVICES_POR_HOST.\n", log_area, "error")
                time.sleep(0.5)
                continue
            append_log_color(f"[{host}] → Conexión SSH para estado de servicios...\n", log_area, None)
            try:
                cliente = paramiko.SSHClient()
                cliente.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                cliente.connect(
                    hostname=host,
                    port=SSH_PORT,
                    username=USERNAME,
                    password=PASSWORD,
                    timeout=10
                )
                for servicio in servicios:
                    cmd_is_active = f"echo '{PASSWORD}' | sudo -S systemctl is-active {servicio}"
                    stdin1, stdout1, stderr1 = cliente.exec_command(cmd_is_active)
                    salida1 = stdout1.read().decode("utf-8", errors="ignore").strip()
                    _ = stderr1.read()
                    if salida1 == "active":
                        append_log_color(f"[{host}] → Servicio {servicio}: ACTIVO\n", log_area, "success")
                    else:
                        append_log_color(f"[{host}] → Servicio {servicio}: INACTIVO\n", log_area, "error")
                    cmd_status = f"echo '{PASSWORD}' | sudo -S systemctl status {servicio} --no-pager -n 3"
                    stdin2, stdout2, stderr2 = cliente.exec_command(cmd_status)
                    lines = stdout2.read().decode("utf-8", errors="ignore").splitlines()
                    _ = stderr2.read()
                    if lines:
                        append_log_color(f"[{host}] → Fragmento de status de {servicio}:\n", log_area, None)
                        for l in lines[-3:]:
                            append_log_color(f"    {l}\n", log_area, None)
                    else:
                        append_log_color(f"[{host}] → No se pudo obtener status para {servicio} (o está vacío)\n", log_area, "error")
                    append_log_color("\n", log_area, None)
                cliente.close()
                append_log_color(f"[{host}] → Verificación finalizada.\n\n", log_area, None)
            except Exception as e:
                append_log_color(f"[{host}] → EXCEPCIÓN al verificar estado: {e}\n\n", log_area, "error")
            time.sleep(0.5)
        append_log_color(f"==== [{bloque_nombre}] Estado de servicios finalizado ====\n", log_area, None)
    threading.Thread(target=tarea_estado, daemon=True).start()

def ejecutar_actualizargit(host: str, log_callback):
    log_callback(f"[{host}] → Conexión SSH para actualizar gits...", None)
    try:
        cliente = paramiko.SSHClient()
        cliente.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        cliente.connect(
            hostname=host,
            port=SSH_PORT,
            username=USERNAME,
            password=PASSWORD,
            timeout=10
        )
        comando = f"python3 {UPDATE_SCRIPT_PATH}"
        stdin, stdout, stderr = cliente.exec_command(comando)
        for line in stdout:
            line = line.rstrip("\n")
            if line:
                log_callback(f"[{host}] → STDOUT: {line}", None)
        for line in stderr:
            line = line.rstrip("\n")
            if line:
                log_callback(f"[{host}] → STDERR: {line}", None)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            log_callback(f"[{host}] → actualizargit.py completado con éxito (exit code = 0).", "success")
        else:
            log_callback(f"[{host}] → actualizargit.py ERROR (exit code = {exit_status}).", "error")
        cliente.close()
        log_callback(f"[{host}] → Conexión finalizada.\n", None)
    except Exception as e:
        log_callback(f"[{host}] → EXCEPCIÓN al actualizar gits: {e}\n", "error")

def ejecutar_actualizar_gits_bloque(hosts: list, log_area: ScrolledText, bloque_nombre: str):
    def tarea_gits():
        log_area.configure(state="normal")
        log_area.delete("1.0", tk.END)
        log_area.insert(tk.END, f"==== [{bloque_nombre}] Actualizando Gits en hosts ====\n\n")
        log_area.configure(state="disabled")
        for h in hosts:
            ejecutar_actualizargit(
                host=h,
                log_callback=lambda texto, tag=None: append_log_color(texto, log_area, tag)
            )
            time.sleep(0.5)
        append_log_color(f"==== [{bloque_nombre}] Actualización de Gits completada ====\n", log_area, None)
    threading.Thread(target=tarea_gits, daemon=True).start()

# ---- Ejecutar REBOOT o SHUTDOWN ----
def ejecutar_accion_servidor(host, accion, log_area):
    """
    accion: "reboot" o "shutdown"
    """
    cmd = "reboot" if accion == "reboot" else "shutdown -h now"
    def worker():
        append_log_color(f"[{host}] → Ejecutando sudo {cmd}...", log_area)
        try:
            cliente = paramiko.SSHClient()
            cliente.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cliente.connect(host, port=SSH_PORT, username=USERNAME, password=PASSWORD, timeout=10)
            comando = f"echo '{PASSWORD}' | sudo -S {cmd}"
            stdin, stdout, stderr = cliente.exec_command(comando, get_pty=True)
            for line in stdout:
                append_log_color(f"[{host}] {line.rstrip()}", log_area)
            for line in stderr:
                append_log_color(f"[{host}] ERR {line.rstrip()}", log_area, "error")
            code = stdout.channel.recv_exit_status()
            append_log_color(f"[{host}] → Exit code {code}", log_area, "success" if code == 0 else "error")
            cliente.close()
        except Exception as e:
            append_log_color(f"[{host}] → EXCEPCIÓN: {e}", log_area, "error")
    threading.Thread(target=worker, daemon=True).start()

def crear_ui():
    root = tk.Tk()
    root.title("Panel de Control de Módulos Remotos")
    root.attributes("-fullscreen", True)
    root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))
    frame_botones = tk.Frame(root)
    frame_botones.pack(fill="x", padx=10, pady=10)

    # ---- Menú Receptores ----
    mb_receptores = tk.Menubutton(frame_botones, text="Receptores", relief="raised", width=15)
    menu_receptores = tk.Menu(mb_receptores, tearoff=0)
    menu_receptores.add_command(
        label="Iniciar módulos",
        command=lambda: ejecutar_para_hosts(HOSTS_RECEPTORES, OPTIONS["Iniciar módulos"], log_area, "Receptores")
    )
    menu_receptores.add_command(
        label="Detener módulos",
        command=lambda: ejecutar_para_hosts(HOSTS_RECEPTORES, OPTIONS["Detener módulos"], log_area, "Receptores")
    )
    menu_receptores.add_command(
        label="Reiniciar módulos",
        command=lambda: ejecutar_para_hosts(HOSTS_RECEPTORES, OPTIONS["Reiniciar módulos"], log_area, "Receptores")
    )
    menu_receptores.add_separator()
    menu_receptores.add_command(
        label="Ver estado de servicios",
        command=lambda: verificar_estado_bloque(HOSTS_RECEPTORES, log_area, "Receptores")
    )
    menu_receptores.add_command(
        label="Actualizar Gits",
        command=lambda: ejecutar_actualizar_gits_bloque(HOSTS_RECEPTORES, log_area, "Receptores")
    )
    mb_receptores.config(menu=menu_receptores)
    mb_receptores.pack(side="left", padx=5)

    # ---- Menú Paseadores ----
    mb_paseadores = tk.Menubutton(frame_botones, text="Paseadores", relief="raised", width=15)
    menu_paseadores = tk.Menu(mb_paseadores, tearoff=0)
    menu_paseadores.add_command(
        label="Iniciar módulos",
        command=lambda: ejecutar_para_hosts(HOSTS_PASEADORES, OPTIONS["Iniciar módulos"], log_area, "Paseadores")
    )
    menu_paseadores.add_command(
        label="Detener módulos",
        command=lambda: ejecutar_para_hosts(HOSTS_PASEADORES, OPTIONS["Detener módulos"], log_area, "Paseadores")
    )
    menu_paseadores.add_command(
        label="Reiniciar módulos",
        command=lambda: ejecutar_para_hosts(HOSTS_PASEADORES, OPTIONS["Reiniciar módulos"], log_area, "Paseadores")
    )
    menu_paseadores.add_separator()
    menu_paseadores.add_command(
        label="Ver estado de servicios",
        command=lambda: verificar_estado_bloque(HOSTS_PASEADORES, log_area, "Paseadores")
    )
    menu_paseadores.add_command(
        label="Actualizar Gits",
        command=lambda: ejecutar_actualizar_gits_bloque(HOSTS_PASEADORES, log_area, "Paseadores")
    )
    mb_paseadores.config(menu=menu_paseadores)
    mb_paseadores.pack(side="left", padx=5)

    # ---- Menú Terminales ----
    mb_terminales = tk.Menubutton(frame_botones, text="Terminales", relief="raised", width=15)
    menu_terminales = tk.Menu(mb_terminales, tearoff=0)
    # Submenú Receptores
    sub_menu_receptores = tk.Menu(menu_terminales, tearoff=0)
    for host in HOSTS_RECEPTORES:
        sub_menu_receptores.add_command(
            label=host,
            command=lambda host=host: open_terminal_embedded(host)
        )
    menu_terminales.add_cascade(label="Receptores", menu=sub_menu_receptores)
    # Submenú Paseadores
    sub_menu_paseadores = tk.Menu(menu_terminales, tearoff=0)
    for host in HOSTS_PASEADORES:
        sub_menu_paseadores.add_command(
            label=host,
            command=lambda host=host: open_terminal_embedded(host)
        )
    menu_terminales.add_cascade(label="Paseadores", menu=sub_menu_paseadores)
    mb_terminales.config(menu=menu_terminales)
    mb_terminales.pack(side="left", padx=5)

    # ---- Menú Servidores ----
    mb_servidores = tk.Menubutton(frame_botones, text="Servidores", relief="raised", width=15)
    menu_servidores = tk.Menu(mb_servidores, tearoff=0)
    # Submenú Receptores
    sub_menu_receptores_srv = tk.Menu(menu_servidores, tearoff=0)
    for host in HOSTS_RECEPTORES:
        def make_action_menu(h):
            menu = tk.Menu(sub_menu_receptores_srv, tearoff=0)
            menu.add_command(
                label="Reiniciar servidor",
                command=lambda h=h: ejecutar_accion_servidor(h, "reboot", log_area)
            )
            menu.add_command(
                label="Apagar servidor",
                command=lambda h=h: ejecutar_accion_servidor(h, "shutdown", log_area)
            )
            return menu
        action_menu = make_action_menu(host)
        sub_menu_receptores_srv.add_cascade(label=host, menu=action_menu)
    menu_servidores.add_cascade(label="Receptores", menu=sub_menu_receptores_srv)
    # Submenú Paseadores
    sub_menu_paseadores_srv = tk.Menu(menu_servidores, tearoff=0)
    for host in HOSTS_PASEADORES:
        def make_action_menu_p(h):
            menu = tk.Menu(sub_menu_paseadores_srv, tearoff=0)
            menu.add_command(
                label="Reiniciar servidor",
                command=lambda h=h: ejecutar_accion_servidor(h, "reboot", log_area)
            )
            menu.add_command(
                label="Apagar servidor",
                command=lambda h=h: ejecutar_accion_servidor(h, "shutdown", log_area)
            )
            return menu
        action_menu_p = make_action_menu_p(host)
        sub_menu_paseadores_srv.add_cascade(label=host, menu=action_menu_p)
    menu_servidores.add_cascade(label="Paseadores", menu=sub_menu_paseadores_srv)
    mb_servidores.config(menu=menu_servidores)
    mb_servidores.pack(side="left", padx=5)

    # ---- Botón Salir ----
    btn_salir = tk.Button(
        frame_botones, text="Salir", width=10, padx=5, pady=5, command=lambda: root.quit()
    )
    btn_salir.pack(side="right", padx=5)

    # ---- Área de logs ----
    global log_area
    log_area = ScrolledText(root, state="disabled", wrap="word", height=30)
    log_area.pack(fill="both", padx=10, pady=(0,10), expand=True)
    log_area.tag_configure("success", foreground="green")
    log_area.tag_configure("error", foreground="red")
    log_area.configure(state="normal")
    log_area.insert(tk.END, "» Bienvenido al Panel de Control de Módulos Remotos\n\n")
    log_area.configure(state="disabled")
    root.mainloop()

if __name__ == "__main__":
    crear_ui()
