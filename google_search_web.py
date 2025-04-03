#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Aplicativo simples de pesquisa Google com notificação web no Android
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

class NotificacaoRequestHandler(BaseHTTPRequestHandler):
    """Manipulador de solicitações HTTP para o servidor de notificações"""
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            with open('index.html', 'rb') as file:
                self.wfile.write(file.read())
        
        # Endpoint para receber notificações
        elif self.path == '/notifications':
            self.send_response(200)
            self.send_header('Content-type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            
            try:
                # Enviar um evento inicial para confirmar conexão
                msg = 'data: {"tipo":"conexao","mensagem":"Conectado"}\n\n'.encode('utf-8')
                self.wfile.write(msg)
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
            except Exception as e:
                print(f"Erro no streaming: {e}")
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
    
    notificacoes = []  # Lista para armazenar notificações
    server = None
    url = None
    
    @classmethod
    def iniciar_servidor(cls):
        """Inicia o servidor HTTP"""
        # Tenta encontrar um IP local para o servidor
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.254.254.254', 1))
            ip_local = s.getsockname()[0]
        except Exception:
            ip_local = '127.0.0.1'
        finally:
            s.close()
        
        # Criar arquivo HTML para interface
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write('''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Notificações de Pesquisa</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .notification {
            background-color: white;
            border-left: 4px solid #4285f4;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 15px;
            padding: 15px;
        }
        .notification h2 {
            margin-top: 0;
            color: #4285f4;
        }
        .notification a {
            color: #1a73e8;
            text-decoration: none;
            display: block;
            margin: 8px 0;
        }
        .header {
            text-align: center;
            margin-bottom: 20px;
        }
        button {
            background-color: #4285f4;
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 4px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Notificações de Pesquisa Google</h1>
        <p>Mantenha esta página aberta para receber notificações</p>
        <button id="notifyBtn">Ativar Notificações</button>
    </div>
    
    <div id="notifications">
        <!-- As notificações serão inseridas aqui -->
    </div>

    <script>
        // Solicitar permissão de notificação
        document.getElementById('notifyBtn').addEventListener('click',  
        function() {
            Notification.requestPermission();
            alert("Notificações ativadas!");
        });
        
        // Configurar Event Source
        const eventSource = new EventSource('/notifications');
        
        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            
            if (data.tipo === 'conexao') {
                console.log('Conectado ao servidor');
                return;
            }
            
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
            document.getElementById('notifications').prepend(notifDiv);
            
            // Enviar notificação do navegador
            if (Notification.permission === 'granted') {
                new Notification('Nova Pesquisa', {
                    body: data.titulo
                });
            }
            
            // Vibrar dispositivo se suportado
            if (navigator.vibrate) {
                navigator.vibrate(200);
            }
        };
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
        print("[+] Clique em 'Ativar Notificações' quando a página abrir")
        
        # Iniciar servidor em uma thread separada
        thread = threading.Thread(target=cls.server.serve_forever)
        thread.daemon = True
        thread.start()
        
        # Tentar abrir o navegador
        try:
            webbrowser.open(cls.url)
        except:
            pass
        
        return cls.url
    
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
    """Pesquisa no Google e retorna os resultados"""
    print(f"Pesquisando por: {consulta}")
    resultados = []
    
    try:
        for url in search(consulta, num_results=num_resultados):
            resultados.append(url)
            print(f"Encontrado: {url}")
    except Exception as e:
        print(f"Erro na pesquisa: {e}")
        return []
    
    return resultados

def obter_titulo_pagina(url):
    """Extrai o título da página web"""
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
    """Função principal do aplicativo"""
    print("Iniciando aplicativo de pesquisa Google...")
    
    # Iniciar servidor para notificações
    NotificacaoServer.iniciar_servidor()
    time.sleep(2)  # Dar tempo para o servidor iniciar
    
    print("\n========== INSTRUÇÕES ==========")
    print("1. Abra o link acima no navegador do seu celular")
    print("2. Clique no botão 'Ativar Notificações'")
    print("3. Faça pesquisas digitando os termos abaixo")
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
