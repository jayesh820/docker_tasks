import streamlit as st
import docker
import paramiko
from docker.errors import DockerException
import io
import time

# -----------------------
# CONFIG
# -----------------------
DEFAULT_DOCKER_HOST = "tcp://localhost:2375"  # Local Docker TCP
DEFAULT_SSH_HOST = ""
DEFAULT_SSH_USER = ""
DEFAULT_SSH_PASS = ""


# -----------------------
# FUNCTIONS
# -----------------------
@st.cache_resource
def get_docker_client_via_tcp(docker_host):
    try:
        client = docker.DockerClient(base_url=docker_host)
        client.ping()
        return client
    except DockerException as e:
        st.error(f"Failed to connect to Docker daemon at {docker_host}.\nError: {e}")
        return None


def run_ssh_command(host, username, password, command):
    """Run command on remote server via SSH."""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=username, password=password, timeout=10)
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode()
        error = stderr.read().decode()
        ssh.close()
        return output if output else error
    except Exception as e:
        return f"SSH connection error: {e}"


# -----------------------
# MAIN APP
# -----------------------
def main():
    st.title("🐳 Advanced Docker Management Panel (with SSH Support)")

    # Connection Mode
    mode = st.radio("Choose Connection Method", ["Local Docker TCP", "SSH to Remote Docker"])

    if mode == "Local Docker TCP":
        docker_host = st.text_input("Docker Host", value=DEFAULT_DOCKER_HOST)
        client = get_docker_client_via_tcp(docker_host)
        if not client:
            st.stop()

    else:
        ssh_host = st.text_input("SSH Host", value=DEFAULT_SSH_HOST)
        ssh_user = st.text_input("SSH Username", value=DEFAULT_SSH_USER)
        ssh_pass = st.text_input("SSH Password", type="password", value=DEFAULT_SSH_PASS)

        if st.button("Test SSH Connection"):
            result = run_ssh_command(ssh_host, ssh_user, ssh_pass, "docker ps -a")
            st.code(result)

        st.warning("SSH mode uses remote Docker CLI via commands — limited UI features.")

    st.markdown("---")
    tab1, tab2, tab3, tab4 = st.tabs(["📦 Containers", "🖼 Images", "📜 Logs", "⚡ Exec Inside Container"])

    # 1️⃣ Containers Management
    with tab1:
        st.subheader("Containers List")
        containers = client.containers.list(all=True) if mode == "Local Docker TCP" else []
        search = st.text_input("Search container by name")

        filtered = [c for c in containers if search.lower() in c.name.lower()] if search else containers

        if filtered:
            container_options = {f"{c.name} ({c.short_id})": c for c in filtered}
            selected = st.selectbox("Select Container", list(container_options.keys()))
            container = container_options[selected]

            st.write(f"**Image:** {container.image.tags}")
            st.write(f"**Status:** {container.status}")

            col1, col2, col3, col4 = st.columns(4)
            if col1.button("Start"):
                container.start(); st.success("Started.")
            if col2.button("Stop"):
                container.stop(); st.success("Stopped.")
            if col3.button("Restart"):
                container.restart(); st.success("Restarted.")
            if col4.button("Remove", type="primary"):
                container.remove(force=True); st.success("Removed.")

            # Live stats
            if st.checkbox("Show Live Stats"):
                stats = container.stats(stream=False)
                mem = stats["memory_stats"]["usage"] / (1024 ** 2)
                cpu = stats["cpu_stats"]["cpu_usage"]["total_usage"]
                st.info(f"Memory: {mem:.2f} MB | CPU: {cpu} units")

        else:
            st.info("No containers found.")

        # Create container
        st.subheader("Create New Container")
        img = st.text_input("Image name", "alpine:latest")
        cmd = st.text_input("Command", "echo Hello from Docker")
        if st.button("Create & Run"):
            try:
                new_c = client.containers.run(img, cmd or None, detach=True)
                st.success(f"Started new container: {new_c.short_id}")
            except Exception as e:
                st.error(str(e))

    # 2️⃣ Images Management
    with tab2:
        st.subheader("Docker Images")
        images = client.images.list() if mode == "Local Docker TCP" else []
        search_img = st.text_input("Search image")
        filtered_img = [i for i in images if any(search_img in tag for tag in i.tags)] if search_img else images

        for img in filtered_img:
            st.write(f"ID: {img.short_id} | Tags: {img.tags}")
            if st.button(f"Remove {img.short_id}"):
                try:
                    client.images.remove(img.id, force=True)
                    st.success("Image removed")
                except Exception as e:
                    st.error(str(e))

        st.markdown("### Pull New Image")
        new_image = st.text_input("Image to pull", "nginx:latest")
        if st.button("Pull Image"):
            try:
                client.images.pull(new_image)
                st.success("Image pulled successfully")
            except Exception as e:
                st.error(str(e))

    # 3️⃣ Logs Viewer
    with tab3:
        if mode == "Local Docker TCP" and containers:
            log_container = st.selectbox("Select container for logs", [c.name for c in containers])
            c = next(cc for cc in containers if cc.name == log_container)
            logs = c.logs(tail=50).decode()
            st.code(logs)
            if st.button("Download Logs"):
                st.download_button("Download Logs", logs, file_name=f"{log_container}_logs.txt")
        else:
            st.info("Logs available only in Local TCP mode.")

    # 4️⃣ Exec Inside Container
    with tab4:
        if mode == "Local Docker TCP" and containers:
            exec_container = st.selectbox("Select container to exec", [c.name for c in containers])
            c = next(cc for cc in containers if cc.name == exec_container)
            command = st.text_input("Command to run", "ls -l")
            if st.button("Run Command"):
                exec_id = client.api.exec_create(c.id, command)
                output = client.api.exec_start(exec_id).decode()
                st.code(output)
        else:
            st.info("Exec available only in Local TCP mode.")


if __name__ == "__main__":
    main()
