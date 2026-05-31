"""
test_camera.py

Script rápido para testar se a câmera IP está acessível e
se o OpenCV consegue capturar frames dela.
Execute diretamente pelo terminal antes de subir o sistema completo.
"""

import cv2
import sys

# ─── CONFIGURAÇÃO ───────────────────────────────────────────
IP       = "192.168.1.100"   # Troque pelo IP da sua câmera
USER     = "admin"            # Troque pelo usuário
PASSWORD = "senha"            # Troque pela senha
PORT     = 554
STREAM   = "stream"           # Pode variar por marca
# ────────────────────────────────────────────────────────────

# Monta a URL RTSP
url = f"rtsp://{USER}:{PASSWORD}@{IP}:{PORT}/{STREAM}"
print(f"Conectando em: {url}")

# Tenta abrir a conexão
cap = cv2.VideoCapture(url)

if not cap.isOpened():
    print("❌ Falha ao conectar. Verifique IP, usuário, senha e porta.")
    sys.exit(1)

print("✅ Câmera conectada! Pressione 'q' para sair.")

while True:
    ret, frame = cap.read()

    if not ret:
        print("⚠️  Frame não recebido. Stream pode ter caído.")
        break

    # Exibe o frame numa janela
    cv2.imshow("Teste - Câmera IP", frame)

    # Pressione 'q' para encerrar
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Conexão encerrada.")