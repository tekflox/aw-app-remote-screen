---
repo: architecture
path: docs/architecture/aw-app-remote-screen.md
source: generated
edited: false
checksum: sha256:ff8140c400cc9eb9287821c1f7d641228b3438d53905610e43af88b705aafff7
---
# Remote Screen

- **repo**: aw-app-remote-screen
- **layer**: app
- **technologies**: python, react
- **health** (derived): planned

Remote screens in the browser, three protocols behind one viewer: VNC (noVNC over a raw WebSocket->TCP byte bridge), RDP (same bridge, pending a browser-side client), and Android (live ~2 fps screen mirror + tap/swipe/text/key input over the remote-agent exec channel — no VNC server involved). Hosts live in this app's own Postgres table with per-app SQL migrations; passwords in the workspace secret store. Ports the monolith's src/api/routes/remote_desktop.py + android_viewer.py + RemoteDesktopWindow.jsx.

## Connections
- `db` → **postgres** — app-owned tables in the workspace schema
- `http` → **aw-workspace** — routes mounted at /api/apps/remote-screen

## MCP tools
_none exposed_

## Requirements
### Entrada de controle malformada é descartada em vez de derrubar a sessão
- Given um fluxo de mensagens de controle vindo do navegador durante um espelhamento vivo, onde um frame pode chegar truncado ou com tipo desconhecido
- When a mensagem é traduzida em comando (repos/aw-app-remote-screen/remote_screen_app/android.py::build_input_command:222)
- Then a função devolve None para coordenada não numérica, texto vazio, tipo desconhecido e keycode inválido, em vez de levantar exceção — devolver None mantém um frame de lixo de destruir uma sessão de espelhamento inteira, que é o que uma exceção faria no meio de um WebSocket. É uma escolha de robustez com custo assumido: entrada inválida some silenciosamente, sem nada dizer a quem clicou
- intended_status: `not_implemented` · derived health: `not_implemented`
- tests: `repos/aw-app-remote-screen/tests/test_store_and_routes.py` (passing)

### Keycode é validado por allow-list, não escapado, porque roda na máquina remota
- Given o keycode chega do navegador e é interpolado num comando que executa na máquina remota
- When o valor é conferido caractere a caractere antes de virar comando (repos/aw-app-remote-screen/remote_screen_app/android.py:264)
- Then só alfanumérico e underscore passam, então "HOME; rm -rf /" e "$(whoami)" são recusados por completo — a escolha aqui é rejeitar em vez de shell-quotar, e ela é deliberada: um keycode legítimo nunca precisa de caractere especial, então uma allow-list estreita não custa nada e não depende de o quoting estar certo. O texto livre, esse sim, é shell-quotado (android.py:256), porque ali o conteúdo arbitrário é o próprio ponto
- intended_status: `not_implemented` · derived health: `not_implemented`
- tests: `repos/aw-app-remote-screen/tests/test_store_and_routes.py` (passing)

### Salvar um host sem informar senha mantém a que já estava guardada
- Given um host já cadastrado com senha, e uma edição que muda só o nome ou a porta e por isso não reenvia a senha
- When o update é aplicado (repos/aw-app-remote-screen/remote_screen_app/store.py, exercitado por repos/aw-app-remote-screen/tests/test_store_and_routes.py::test_update_without_password_keeps_the_saved_one:53)
- Then o segredo salvo sobrevive, apagá-lo exige um pedido explícito de limpeza (test_clear_password_removes_the_secret:62) e deletar o host purga o segredo junto (test_delete_purges_the_secret_too:78) — a listagem nunca devolve a senha, só o endpoint de credenciais devolve. Tratar campo ausente como "apagar" é o erro clássico de CRUD com segredo: a pessoa corrige um typo no nome e descobre depois que perdeu a senha, sem nada ter avisado
- intended_status: `not_implemented` · derived health: `not_implemented`
- tests: `repos/aw-app-remote-screen/tests/test_store_and_routes.py` (passing)

### Cada protocolo exige o que faz sentido para ele, e o não suportado é guardável mas sinalizado
- Given os três protocolos que o app cobre têm formas diferentes: VNC precisa de porta, Android é alcançado por serial de dispositivo, e RDP ainda não é servido
- When a validação por tipo roda (repos/aw-app-remote-screen/remote_screen_app/store.py, via test_vnc_still_requires_a_port:173, test_android_host_needs_no_port:164 e test_rdp_is_storable_but_flagged_unsupported:100)
- Then VNC sem porta é recusado, Android é aceito sem porta, RDP é armazenado mas marcado como não suportado, e os endpoints Android respondem 400 para um host VNC (test_android_endpoints_reject_a_vnc_host:228) — guardar o RDP em vez de recusar deixa a configuração pronta para quando o transporte existir, e a flag é o que impede isso de virar promessa: um host que salva sem aviso e depois não conecta parece bug, não escopo
- intended_status: `not_implemented` · derived health: `not_implemented`
- tests: `repos/aw-app-remote-screen/tests/test_store_and_routes.py` (passing)

### O comando adb só é escopado por dispositivo quando existe um serial
- Given uma máquina remota que pode ter um único dispositivo conectado ou vários
- When o prefixo do comando é montado (repos/aw-app-remote-screen/remote_screen_app/android.py::adb:79)
- Then com serial preenchido sai `adb -s &lt;serial&gt;` e com serial em branco sai `adb` puro, deixando o próprio adb escolher o único dispositivo ligado — passar `-s ""` faria toda chamada falhar em um cenário de dispositivo único, que é o caso mais comum, e o erro do adb nesse caso não deixa claro que a culpa é de um campo vazio no cadastro. O tamanho da tela também é usado para desnormalizar coordenadas quando disponível (android.py:229), de modo que um clique feito num navegador de outra resolução ainda cai no lugar certo
- intended_status: `not_implemented` · derived health: `not_implemented`
- tests: `repos/aw-app-remote-screen/tests/test_store_and_routes.py` (passing)
