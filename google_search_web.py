#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Aplicativo de pesquisa Google com notificação web no Android
"""

import requests
from bs4 import BeautifulSoup
from googlesearch import search
import time
import json
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import socket
import urllib.parse
import os
import qrcode  # Você pode precisar instalar com: pip install qrcode pillow

"""
INSTRUÇÕES DE INSTALAÇÃO NO TERMUX:

1. Abra o Termux e execute os seguintes comandos:
pkg update && pkg upgrade
pkg install python
pip install googlesearch-python requests beautifulsoup4 qrcode pillow
"""

class NotificacaoRequestHandler(BaseHTTPRequestHandler):
    """Manipulador de solicitações HTTP para o servidor de notificações"""
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            with open('index.html', 'rb') as file:
                self.wfile.write(file.read())
        
        # Endpoint para verificar se o servidor está ativo
        elif self.path == '/ping':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'pong')
        
        # Endpoint para receber notificações via SSE
        elif self.path == '/notifications':
            self.send_response(200)
            self.send_header('Content-type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            
            try:
                # Enviar um evento inicial para confirmar conexão
                self.wfile.write(b'data: {"tipo":"conexao","mensagem":"Conectado ao servidor de notificações"}\n\n')
                self.wfile.flush()
                
                # Manter a conexão aberta
                while True:
                    # Verifica se há novas notificações
                    if len(NotificacaoServer.notificacoes) > 0:
                        notificacao = NotificacaoServer.notificacoes.pop(0)
                        encoded_data = "data: " + json.dumps(notificacao) + "\n\n"
                        try:
                            self.wfile.write(encoded_data.encode('utf-8'))
                            self.wfile.flush()
                        except:
                            break
                    time.sleep(0.5)
            except BrokenPipeError:
                print("Cliente desconectou")
            except Exception as e:
                print(f"Erro no streaming de eventos: {e}")
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'404 Not Found')
    
    def log_message(self, format, *args):
        # Desabilitar logs de acesso do servidor
        return

class NotificacaoServer:
    """Servidor para enviar notificações ao navegador"""
    
    notificacoes = []  # Lista para armazenar notificações a serem enviadas
    server = None
    url = None
    
    @classmethod
    def iniciar_servidor(cls):
        """Inicia o servidor HTTP"""
        # Tenta encontrar um IP local para o servidor
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Não precisamos realmente conectar
            s.connect(('10.254.254.254', 1))
            ip_local = s.getsockname()[0]
        except Exception:
            ip_local = '127.0.0.1'
        finally:
            s.close()
        
        # Criar arquivo HTML para interface do usuário
        with open('index.html', 'w') as f:
            f.write('''
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Notificações de Pesquisa</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f9f9f9;
            color: #333;
        }
        .notification {
            background-color: white;
            border-left: 4px solid #4285f4;
            border-radius: 8px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            padding: 20px;
            transition: all 0.3s ease;
            animation: fadeIn 0.5s;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .notification h2 {
            margin-top: 0;
            color: #4285f4;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
        }
        .notification a {
            color: #1a73e8;
            text-decoration: none;
            display: block;
            margin: 10px 0;
            padding: 10px;
            border-radius: 4px;
            background-color: #f5f8ff;
            transition: background-color 0.2s;
        }
        .notification a:hover {
            background-color: #e8f0fe;
        }
        .notification-container {
            max-width: 800px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            border-bottom: 1px solid #eee;
        }
        .header h1 {
            color: #4285f4;
            margin-bottom: 5px;
        }
        .header p {
            color: #666;
            margin-top: 5px;
        }
        .toast {
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            background-color: #4285f4;
            color: white;
            padding: 16px 32px;
            border-radius: 50px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            opacity: 0;
            transition: opacity 0.3s, transform 0.3s;
            z-index: 1000;
            font-weight: 500;
        }
        .toast.show {
            opacity: 1;
            transform: translateX(-50%) translateY(-10px);
        }
        .status {
            text-align: center;
            padding: 10px;
            margin: 20px 0;
            border-radius: 4px;
            background-color: #e2f3eb;
            color: #137333;
        }
        .btn {
            background-color: #4285f4;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            margin: 10px auto;
            display: block;
        }
        .btn:hover {
            background-color: #3367d6;
        }
        #connectionStatus {
            position: fixed;
            top: 10px;
            right: 10px;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            background-color: #f44336;
            color: white;
            transition: background-color 0.3s;
        }
        #connectionStatus.connected {
            background-color: #4caf50;
        }
        .empty-state {
            text-align: center;
            color: #666;
            margin-top: 50px;
        }
        .empty-state i {
            font-size: 50px;
            color: #ddd;
        }
    </style>
</head>
<body>
    <div id="connectionStatus">Desconectado</div>
    
    <div class="header">
        <h1>Notificações de Pesquisa Google</h1>
        <p>Resultados de pesquisa em tempo real</p>
    </div>
    
    <div class="notification-container">
        <div id="welcome-message" class="notification">
            <h2>Bem-vindo ao Aplicativo de Pesquisa</h2>
            <p>Mantenha esta página aberta para receber notificações de pesquisas realizadas no Termux.</p>
            <button id="enableNotifications" class="btn">Ativar Notificações</button>
        </div>
        
        <div id="notifications">
            <!-- As notificações serão inseridas aqui -->
        </div>
        
        <div id="empty-state" class="empty-state">
            <p>Nenhuma pesquisa realizada ainda. Faça uma pesquisa no terminal Termux.</p>
        </div>
    </div>

    <div id="toast" class="toast"></div>

    <script>
        let isConnected = false;
        const connectionStatus = document.getElementById('connectionStatus');
        const notificationsContainer = document.getElementById('notifications');
        const emptyState = document.getElementById('empty-state');
        
        // Solicitar permissão para notificações
        document.getElementById('enableNotifications').addEventListener('click', async () => {
            try {
                const permission = await Notification.requestPermission();
                if (permission === 'granted') {
                    showToast('Notificações ativadas com sucesso!');
                } else {
                    showToast('Permissão para notificações negada');
                }
            } catch (err) {
                console.error('Erro ao solicitar permissão:', err);
                showToast('Erro ao ativar notificações');
            }
        });
        
        // Verificar se o servidor está ativo
        function checkServerConnection() {
            fetch('/ping')
                .then(() => {
                    if (!isConnected) {
                        isConnected = true;
                        connectionStatus.textContent = 'Conectado';
                        connectionStatus.classList.add('connected');
                    }
                })
                .catch(() => {
                    isConnected = false;
                    connectionStatus.textContent = 'Desconectado';
                    connectionStatus.classList.remove('connected');
                });
        }
        
        // Verificar conexão a cada 5 segundos
        setInterval(checkServerConnection, 5000);
        
        // Configurar Event Source para receber notificações
        function setupEventSource() {
            const eventSource = new EventSource('/notifications');
            
            eventSource.onopen = function() {
                isConnected = true;
                connectionStatus.textContent = 'Conectado';
                connectionStatus.classList.add('connected');
                console.log('Conexão SSE estabelecida');
            };
            
            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                
                if (data.tipo === 'conexao') {
                    console.log('Conexão confirmada:', data.mensagem);
                    return;
                }
                
                // Ocultar a mensagem de estado vazio
                emptyState.style.display = 'none';
                
                // Criar notificação na página
                const notifDiv = document.createElement('div');
                notifDiv.className = 'notification';
                
                let html = `<h2>${data.titulo}</h2>`;
                
                if (data.links) {
                    data.links.forEach(link => {
                        html += `<a href="${link.url}" target="_blank">${link.titulo}</a>`;
                    });
                } else {
                    html += `<p>${data.mensagem}</p>`;
                }
                
                notifDiv.innerHTML = html;
                
                // Adicionar à página
                notificationsContainer.insertBefore(notifDiv, notificationsContainer.firstChild);
                
                // Mostrar toast
                showToast("Nova pesquisa recebida!");
                
                // Enviar notificação do navegador se permitido
                if (Notification.permission === 'granted') {
                    const notification = new Notification('Nova Pesquisa Google', {
                        body: data.titulo,
                        icon: 'https://www.google.com/favicon.ico'
                    });
                    
                    notification.onclick = function() {
                        window.focus();
                    };
                }
                
                // Vibrar dispositivo se suportado
                if (navigator.vibrate) {
                    navigator.vibrate(200);
                }
            };
            
            eventSource.onerror = function() {
                isConnected = false;
                connectionStatus.textContent = 'Desconectado';
                connectionStatus.classList.remove('connected');
                console.log('Conexão SSE perdida. Tentando reconectar...');
                
                // Tentar reconectar após 3 segundos
                setTimeout(setupEventSource, 3000);
            };
        }
        
        // Iniciar a conexão SSE
        setupEventSource();
        
        function showToast(message) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.classList.add('show');
            
            setTimeout(() => {
                toast.classList.remove('show');
            }, 3000);
        }
        
        // Verificar conexão inicial
        checkServerConnection();
    </script>
</body>
</html>
            ''')
        
        porto = 8080
        servidor_endereco = (ip_local, porto)
        cls.server = HTTPServer(servidor_endereco, NotificacaoRequestHandler)
        cls.url = f"http://{ip_local}:{porto}"
        
        print(f"\n[+] Servidor iniciado em {cls.url}")
        print(f"[+] Abra o link acima no navegador do seu celular")
        print("[+] Mantenha a página aberta para receber notificações")
        
        # Gerar QR Code para facilitar o acesso
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=2,
                border=1,
            )
            qr.add_data(cls.url)
            qr.make(fit=True)
            
            # Imprimir QR code no terminal
            qr.print_ascii()
            print(f"\nEscaneie o QR code acima com seu celular para abrir a página\n")
        except ImportError:
            print("Para gerar QR codes, instale: pip install qrcode")
        except Exception as e:
            print(f"Não foi possível gerar QR code: {e}")
        
        # Iniciar servidor em uma thread separada
        thread = threading.Thread(target=cls.server.serve_forever)
        thread.daemon = True
        thread.start()
        
        # Abrir o navegador automaticamente
        try:
            webbrowser.open(cls.url)
        except:
            pass
        
        return cls.url
    
    @classmethod
    def testar_conexao(cls):
        """Testa se consegue se conectar ao próprio servidor"""
        try:
            if cls.url:
                resposta = requests.get(f"{cls.url}/ping", timeout=2)
                if resposta.status_code == 200 and resposta.text == "pong":
                    print("[✓] Servidor está respondendo corretamente")
                    return True
                else:
                    print("[!] Servidor não está respondendo corretamente")
            return False
        except:
            print("[!] Não foi possível conectar ao servidor")
            return False
    
    @classmethod
    def enviar_notificacao(cls, titulo, mensagem=None, links=None):
        """Envia uma notificação para o navegador"""
        notificacao = {
            'titulo': titulo,
        }
        
        if links:
            notificacao['links'] = links
        else:
            notificacao['mensagem'] = mensagem
            
        cls.notificacoes.append(notificacao)
        print(f"Notificação enviada: {titulo}")
        return True

def pesquisar_no_google(consulta, num_resultados=5):
    """
    Pesquisa no Google e retorna os resultados
    """
    print(f"Pesquisando por: {consulta}")
    resultados = []
    
    try:
        # Realizar a pesquisa usando a biblioteca googlesearch-python
        for url in search(consulta, num_results=num_resultados):
            resultados.append(url)
            print(f"Encontrado: {url}")
    except Exception as e:
        print(f"Erro na pesquisa: {e}")
        return []
    
    return resultados

def obter_titulo_pagina(url):
    """
    Extrai o título da página web
    """
    try:
        resposta = requests.get(url, timeout=5)
        if resposta.status_code == 200:
            soup = BeautifulSoup(resposta.text, 'html.parser')
            titulo = soup.title.string if soup.title else url
            return titulo.strip()
        return url
    except:
        return url

def main():
    """
    Função principal do aplicativo
    """
    print("Iniciando aplicativo de pesquisa Google...")
    
    # Iniciar servidor para notificações
    NotificacaoServer.iniciar_servidor()
    time.sleep(2)  # Dar tempo para o servidor iniciar
    
    # Testar conexão ao servidor
    NotificacaoServer.testar_conexao()
    
    print("\n========== INSTRUÇÕES ==========")
    print("1. Abra o link ou escaneie o QR code acima no navegador do seu celular")
    print("2. Na página que abrir, clique no botão 'Ativar Notificações'")
    print("3. Faça pesquisas digitando os termos abaixo")
    print("4. Mantenha a página do navegador aberta para receber notificações")
    print("==============================\n")
    
    while True:
        # Termo de pesquisa
        consulta = input("\nDigite o termo que deseja pesquisar (ou 'sair' para encerrar): ")
        
        if consulta.lower() == 'sair':
            print("Encerrando aplicativo...")
            break
        
        # Pesquisar no Google
        resultados = pesquisar_no_google(consulta)
        
        if resultados:
            # Preparar links com títulos
            links_formatados = []
            for url in resultados[:5]:
                titulo = obter_titulo_pagina(url)
                links_formatados.append({
                    'titulo': titulo,
                    'url': url
                })
            
            # Enviar notificação com os links
            NotificacaoServer.enviar_notificacao(
                f"Pesquisa: {consulta}",
                links=links_formatados
            )
        else:
            NotificacaoServer.enviar_notificacao(
                "Erro na Pesquisa",
                mensagem=f"Não foi possível encontrar resultados para '{consulta}'"
            )
        
        print("\nVocê pode fazer outra pesquisa ou digitar 'sair'")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAplicativo encerrado pelo usuário")
