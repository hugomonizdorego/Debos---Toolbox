"""Minimal translation layer. English is the source language and the default.

Strings are looked up by their English text, like gettext.  Missing
translations fall back to English, so partial catalogues are fine.
"""

LANGUAGES = {"en": "English", "id": "Bahasa Indonesia", "pt": "Português"}
_current = "en"

_CATALOG = {
    "id": {
        # navigation
        "Overview": "Ikhtisar", "Maintenance": "Perawatan", "Software": "Perangkat Lunak", "System": "Sistem",
        "Personalize": "Personalisasi", "Info": "Info",
        "Dashboard": "Dasbor", "Recommendations": "Rekomendasi", "Cleaner": "Pembersih",
        "Updates & Release": "Pembaruan & Rilis", "Repositories": "Repositori", "APT Sources": "Sumber APT",
        "Software Center": "Pusat Aplikasi", "Uninstall": "Copot Aplikasi", "Desktops & WMs": "Desktop & WM",
        "Kernels": "Kernel", "Drivers": "Driver", "Network": "Jaringan", "System Tweaks": "Tweak Sistem",
        "Desktop Tweaks": "Tweak Desktop", "Startup Apps": "Aplikasi Startup", "Default Apps": "Aplikasi Bawaan",
        "Templates & Scripts": "Templat & Skrip", "Customizer": "Kustomisasi", "About": "Tentang",
        "Search": "Cari",
        # subtitles
        "Your system at a glance": "Sistem Anda dalam sekilas",
        "Smart suggestions to keep Debian healthy": "Saran cerdas agar Debian tetap sehat",
        "Scan and free disk space safely": "Pindai dan kosongkan ruang disk dengan aman",
        "Keep Debian up to date, switch Stable / Testing / Sid": "Jaga Debian tetap terbaru, pindah Stable / Testing / Sid",
        "Official, backports, extrepo and third-party repositories": "Repositori resmi, backports, extrepo dan pihak ketiga",
        "Edit APT source files directly": "Edit berkas sumber APT secara langsung",
        "Install apps from Debian, vendors and Flathub": "Instal aplikasi dari Debian, vendor dan Flathub",
        "Remove installed applications": "Hapus aplikasi yang terpasang",
        "Desktop environments, window managers and login managers": "Lingkungan desktop, window manager dan login manager",
        "Install optimized kernels, build from kernel.org, remove old ones": "Instal kernel teroptimasi, build dari kernel.org, hapus yang lama",
        "Detect hardware and install the right drivers": "Deteksi perangkat keras dan instal driver yang tepat",
        "Diagnostics, DNS, firewall and remote access": "Diagnostik, DNS, firewall dan akses jarak jauh",
        "Performance, security and maintenance tweaks": "Tweak performa, keamanan dan perawatan",
        "Appearance, windows, input and privacy settings": "Pengaturan tampilan, jendela, input dan privasi",
        "Programs that start when you log in": "Program yang berjalan saat Anda masuk",
        "Choose which apps open your files and links": "Pilih aplikasi untuk membuka berkas dan tautan",
        "New-document templates and file manager scripts": "Templat dokumen baru dan skrip pengelola berkas",
        "GRUB, boot splash and login screen": "GRUB, splash boot dan layar login",
        "Version, credits and settings": "Versi, kredit dan pengaturan",
        # common actions
        "Refresh": "Muat Ulang", "Scan": "Pindai", "Clean": "Bersihkan", "Install": "Instal", "Remove": "Hapus",
        "Apply": "Terapkan", "Cancel": "Batal", "Close": "Tutup", "Fix": "Perbaiki", "Fix all": "Perbaiki semua",
        "Open": "Buka", "Enable": "Aktifkan", "Disable": "Nonaktifkan", "Update": "Perbarui", "Upgrade": "Tingkatkan",
        "Continue": "Lanjutkan", "Ignore": "Abaikan", "Details": "Rincian", "Select all": "Pilih semua",
        "Clear selection": "Hapus pilihan", "Installed": "Terpasang", "Current": "Aktif", "Recommended": "Disarankan",
        "Not available": "Tidak tersedia", "Running": "Berjalan", "Loading…": "Memuat…", "Ready": "Siap",
        "Done": "Selesai", "Failed": "Gagal", "Queued": "Antre", "Console": "Konsol", "Stop": "Hentikan",
        "Hide": "Sembunyikan", "Copy log": "Salin log", "Light": "Terang", "Dark": "Gelap", "System theme": "Tema sistem",
        "Language": "Bahasa", "Theme": "Tema", "Settings": "Pengaturan", "Quick actions": "Aksi cepat",
        "Update system": "Perbarui sistem", "Fix packages": "Perbaiki paket", "Free space": "Ruang kosong",
        "Health score": "Skor kesehatan", "Disk": "Disk", "Memory": "Memori", "Updates": "Pembaruan",
        "Packages": "Paket", "Reclaimable": "Dapat dibersihkan", "Uptime": "Waktu aktif", "Health": "Kesehatan",
        "System information": "Informasi sistem", "Top recommendations": "Rekomendasi utama", "See all": "Lihat semua",
        "Everything looks good": "Semuanya terlihat baik", "Search apps, settings or run a command": "Cari aplikasi, pengaturan atau jalankan perintah",
        "Nothing selected.": "Tidak ada yang dipilih.", "Task finished": "Tugas selesai", "Task failed": "Tugas gagal",
        "Are you sure?": "Anda yakin?", "Show script": "Tampilkan skrip", "Run": "Jalankan",
    },
    "pt": {
        "Overview": "Visão geral", "Maintenance": "Manutenção", "Software": "Software", "System": "Sistema",
        "Personalize": "Personalizar", "Info": "Info",
        "Dashboard": "Painel", "Recommendations": "Recomendações", "Cleaner": "Limpeza",
        "Updates & Release": "Atualizações e Versão", "Repositories": "Repositórios", "APT Sources": "Fontes APT",
        "Software Center": "Central de Software", "Uninstall": "Desinstalar", "Desktops & WMs": "Ambientes e WMs",
        "Kernels": "Kernels", "Drivers": "Controladores", "Network": "Rede", "System Tweaks": "Ajustes do Sistema",
        "Desktop Tweaks": "Ajustes do Ambiente", "Startup Apps": "Arranque", "Default Apps": "Aplicações Padrão",
        "Templates & Scripts": "Modelos e Scripts", "Customizer": "Personalizador", "About": "Sobre",
        "Search": "Pesquisar",
        "Your system at a glance": "O seu sistema num relance",
        "Smart suggestions to keep Debian healthy": "Sugestões inteligentes para manter o Debian saudável",
        "Scan and free disk space safely": "Analise e liberte espaço com segurança",
        "Keep Debian up to date, switch Stable / Testing / Sid": "Mantenha o Debian atualizado, mude Stable / Testing / Sid",
        "Official, backports, extrepo and third-party repositories": "Repositórios oficiais, backports, extrepo e de terceiros",
        "Edit APT source files directly": "Edite diretamente os ficheiros de fontes APT",
        "Install apps from Debian, vendors and Flathub": "Instale aplicações do Debian, fornecedores e Flathub",
        "Remove installed applications": "Remova aplicações instaladas",
        "Desktop environments, window managers and login managers": "Ambientes de trabalho, gestores de janelas e de login",
        "Install optimized kernels, build from kernel.org, remove old ones": "Instale kernels otimizados, compile do kernel.org, remova antigos",
        "Detect hardware and install the right drivers": "Detete o hardware e instale os controladores certos",
        "Diagnostics, DNS, firewall and remote access": "Diagnóstico, DNS, firewall e acesso remoto",
        "Performance, security and maintenance tweaks": "Ajustes de desempenho, segurança e manutenção",
        "Appearance, windows, input and privacy settings": "Aparência, janelas, entrada e privacidade",
        "Programs that start when you log in": "Programas que iniciam ao entrar",
        "Choose which apps open your files and links": "Escolha as aplicações para ficheiros e links",
        "New-document templates and file manager scripts": "Modelos de documentos e scripts do gestor de ficheiros",
        "GRUB, boot splash and login screen": "GRUB, ecrã de arranque e ecrã de login",
        "Version, credits and settings": "Versão, créditos e definições",
        "Refresh": "Atualizar", "Scan": "Analisar", "Clean": "Limpar", "Install": "Instalar", "Remove": "Remover",
        "Apply": "Aplicar", "Cancel": "Cancelar", "Close": "Fechar", "Fix": "Corrigir", "Fix all": "Corrigir tudo",
        "Open": "Abrir", "Enable": "Ativar", "Disable": "Desativar", "Update": "Atualizar", "Upgrade": "Atualizar tudo",
        "Continue": "Continuar", "Ignore": "Ignorar", "Details": "Detalhes", "Select all": "Selecionar tudo",
        "Clear selection": "Limpar seleção", "Installed": "Instalado", "Current": "Atual", "Recommended": "Recomendado",
        "Not available": "Indisponível", "Running": "A executar", "Loading…": "A carregar…", "Ready": "Pronto",
        "Done": "Concluído", "Failed": "Falhou", "Queued": "Em fila", "Console": "Consola", "Stop": "Parar",
        "Hide": "Ocultar", "Copy log": "Copiar registo", "Light": "Claro", "Dark": "Escuro", "System theme": "Tema do sistema",
        "Language": "Idioma", "Theme": "Tema", "Settings": "Definições", "Quick actions": "Ações rápidas",
        "Update system": "Atualizar sistema", "Fix packages": "Corrigir pacotes", "Free space": "Espaço livre",
        "Health score": "Pontuação de saúde", "Disk": "Disco", "Memory": "Memória", "Updates": "Atualizações",
        "Packages": "Pacotes", "Reclaimable": "Recuperável", "Uptime": "Tempo ligado", "Health": "Saúde",
        "System information": "Informação do sistema", "Top recommendations": "Principais recomendações", "See all": "Ver tudo",
        "Everything looks good": "Tudo parece bem", "Search apps, settings or run a command": "Pesquise aplicações, definições ou execute um comando",
        "Nothing selected.": "Nada selecionado.", "Task finished": "Tarefa concluída", "Task failed": "Tarefa falhou",
        "Are you sure?": "Tem a certeza?", "Show script": "Mostrar script", "Run": "Executar",
    },
}


def set_language(code):
    global _current
    _current = code if code in LANGUAGES else "en"


def current():
    return _current


def _(text):
    return _CATALOG.get(_current, {}).get(text, text)
