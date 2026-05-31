"""
test_camera_mac.py

Script para testar a câmera embutida do Mac (FaceTime HD).
Usa o índice 0 no VideoCapture, que representa a câmera padrão do sistema.
Útil para validar se o OpenCV está funcionando antes de testar a câmera IP.
"""

import cv2
import sys

# Abre a câmera padrão do Mac (índice 0 = câmera embutida FaceTime HD)
cap = cv2.VideoCapture(0)

# Verifica se a câmera foi acessada com sucesso
if not cap.isOpened():
    print("❌ Não foi possível acessar a câmera. Verifique as permissões.")
    sys.exit(1)

print("✅ Câmera acessada! Pressione 'q' para sair.")

while True:
    # Lê o próximo frame da câmera
    ret, frame = cap.read()

    if not ret:
        print("⚠️ Falha ao capturar frame.")
        break

    # Exibe o frame em uma janela
    cv2.imshow("Teste - Câmera Mac", frame)

    # Pressione 'q' para encerrar
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Libera a câmera e fecha a janela
cap.release()
cv2.destroyAllWindows()
print("Câmera encerrada.")