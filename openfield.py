import PySimpleGUI as sg
import time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg # PySimpleGUI roda sobre Tkinter por padrão

class OpenFieldApp:
    def __init__(self):
        self.test_running = False
        self.start_time = None
        self.remaining_time = 0
        self.animal_id = ""
        self.test_duration = 300 # Duração padrão: 300 segundos (5 minutos)

        # Variáveis para armazenar o tempo acumulado em cada área
        self.corner_time = 0.0
        self.lateral_time = 0.0
        self.center_time = 0.0

        # Variáveis para controlar se um botão de área está atualmente pressionado
        self.corner_button_pressed = False
        self.lateral_button_pressed = False
        self.center_button_pressed = False

        # Variáveis para registrar o tempo de início da pressão do botão
        self.corner_press_time = None
        self.lateral_press_time = None
        self.center_press_time = None

        self.test_data = {} # Para armazenar os resultados do teste atual para o relatório

        self.window = self._create_window()

    def _create_window(self):
        # --- COLUNA DA ESQUERDA: Aplicação de Teste ---
        left_column_layout = [
            [sg.Frame('Configurações do Teste', [
                [sg.Text('ID do Animal:'), sg.Input(key='-ANIMAL_ID-', size=(25, 1))],
                [sg.Text('Duração do Teste (segundos):'), sg.Input('300', key='-TEST_DURATION-', size=(10, 1), enable_events=True)]
            ])],
            [sg.Frame('Controle do Teste', [
                [sg.Text('Tempo Restante: 00:00', font=('Helvetica', 24), key='-TIMER_LABEL-', expand_x=True, justification='center')],
                [sg.Button('Iniciar Teste', key='-START_TEST-', button_color=('white', 'green'), size=(15, 2)),
                 sg.Button('Parar Teste', key='-STOP_TEST-', button_color=('white', 'red'), size=(15, 2), disabled=True)]
            ], element_justification='center')],
            [sg.Frame('Marcação de Áreas (Pressione e Segure)', [
                [sg.Button('Canto', key='-CORNER_BTN-', button_color=('white', 'red'), size=(15, 3), disabled=True, enable_events=True),
                 sg.Button('Lateral', key='-LATERAL_BTN-', button_color=('black', 'skyblue'), size=(15, 3), disabled=True, enable_events=True)],
                [sg.Button('Centro', key='-CENTER_BTN-', button_color=('white', 'forestgreen'), size=(32, 3), disabled=True, enable_events=True)],
                [sg.Text('Tempo no Canto: 0.00 s', key='-CORNER_TIME_LABEL-')],
                [sg.Text('Tempo na Lateral: 0.00 s', key='-LATERAL_TIME_LABEL-')],
                [sg.Text('Tempo no Centro: 0.00 s', key='-CENTER_TIME_LABEL-')]
            ], expand_x=True, expand_y=True)],
        ]

        # --- COLUNA DA DIREITA: Relatório e Gráfico ---
        right_column_layout = [
            [sg.Frame('Relatório do Teste', [
                [sg.Multiline(size=(60, 10), key='-REPORT_TEXT-', disabled=True, expand_x=True, expand_y=True)],
                [sg.Button('Gerar/Atualizar Relatório', key='-GENERATE_REPORT-', size=(25, 2)),
                 sg.Button('Exportar Relatório (TXT)', key='-EXPORT_REPORT-', size=(25, 2))]
            ], expand_x=True, expand_y=True)],
            [sg.Frame('Distribuição de Tempo por Área', [
                [sg.Canvas(key='-CANVAS-', size=(500, 400))] # Canvas para o gráfico Matplotlib
            ], expand_x=True, expand_y=True)],
        ]

        # Layout principal com as duas colunas
        layout = [
            [sg.Column(left_column_layout, element_justification='center', expand_x=True, expand_y=True),
             sg.Column(right_column_layout, element_justification='center', expand_x=True, expand_y=True)],
        ]

        return sg.Window('Teste de Campo Aberto', layout, resizable=True, finalize=True)

    def _draw_plot(self, canvas_elem, fig):
        """Desenha o gráfico no Canvas do PySimpleGUI."""
        # Se você estiver usando PySimpleGUI com outro backend (Qt, Wx), esta parte pode mudar
        # Por padrão, PySimpleGUI usa Tkinter, então FigureCanvasTkAgg funciona.
        canvas = FigureCanvasTkAgg(fig, canvas_elem.Widget)
        canvas.draw()
        canvas.get_tk_widget().pack(side='top', fill='both', expand=1)
        return canvas

    def _clear_canvas(self, canvas_elem):
        """Limpa o canvas do PySimpleGUI."""
        for child in canvas_elem.Widget.winfo_children():
            child.destroy()


    def run(self):
        self._current_canvas = None # Para guardar a referência do canvas do matplotlib

        while True:
            event, values = self.window.read(timeout=100) # Atualiza a cada 100ms para o timer

            if event == sg.WIN_CLOSED:
                break

            # --- Eventos de Controle do Teste ---
            if event == '-START_TEST-':
                self.start_test(values)
            elif event == '-STOP_TEST-':
                self.stop_test(manual_stop=True)

            # --- Eventos de Botões de Área (Pressionar/Soltar) ---
            # PySimpleGUI não tem eventos nativos de ButtonPress/Release para Tkinter assim,
            # então usamos enable_events=True no botão e verificamos o nome do evento.
            # A lógica para desativar outros botões e contabilizar o tempo é um pouco mais manual.
            if self.test_running:
                # Lógica para pressionar
                if event == '-CORNER_BTN-':
                    self._on_button_press('Canto')
                elif event == '-LATERAL_BTN-':
                    self._on_button_press('Lateral')
                elif event == '-CENTER_BTN-':
                    self._on_button_press('Centro')

                # PySimpleGUI não tem um evento direto de soltar o mouse para cada botão,
                # então a lógica de "soltar" será baseada na pressão de outro botão
                # ou na parada do teste. O tempo de 'on_update_timer' será a contagem contínua.

            # --- Eventos de Relatório ---
            elif event == '-GENERATE_REPORT-':
                self.generate_report()
            elif event == '-EXPORT_REPORT-':
                self.export_report()

            # --- Atualização do Timer (loop principal) ---
            if self.test_running:
                self.update_timer()

        self.window.close()

    def start_test(self, values):
        if self.test_running:
            return

        self.animal_id = values['-ANIMAL_ID-'].strip()
        if not self.animal_id:
            sg.popup_warning("Por favor, insira o ID do Animal.")
            return

        try:
            duration = int(values['-TEST_DURATION-'])
            if duration <= 0:
                raise ValueError
            self.test_duration = duration
        except ValueError:
            sg.popup_warning("Por favor, insira uma duração de teste válida (número inteiro positivo).")
            return

        self.test_running = True
        self.start_time = time.time()
        self.remaining_time = self.test_duration

        # Resetar todos os tempos e estados
        self.corner_time = 0.0
        self.lateral_time = 0.0
        self.center_time = 0.0
        self.corner_button_pressed = False
        self.lateral_button_pressed = False
        self.center_button_pressed = False
        self.corner_press_time = None
        self.lateral_press_time = None
        self.center_press_time = None
        self.test_data = {}

        self._update_area_time_labels()

        self.window['-START_TEST-'].update(disabled=True)
        self.window['-STOP_TEST-'].update(disabled=False)
        self.window['-CORNER_BTN-'].update(disabled=False)
        self.window['-LATERAL_BTN-'].update(disabled=False)
        self.window['-CENTER_BTN-'].update(disabled=False)

        self._clear_canvas(self.window['-CANVAS-']) # Limpa o gráfico anterior

    def stop_test(self, manual_stop=True):
        if not self.test_running:
            return

        self.test_running = False
        self.window['-START_TEST-'].update(disabled=False)
        self.window['-STOP_TEST-'].update(disabled=True)
        self.window['-CORNER_BTN-'].update(disabled=True)
        self.window['-LATERAL_BTN-'].update(disabled=True)
        self.window['-CENTER_BTN-'].update(disabled=True)

        # Garante que qualquer tempo ativo seja contabilizado ao parar o teste
        if self.corner_button_pressed:
            self._on_button_release('Canto')
        if self.lateral_button_pressed:
            self._on_button_release('Lateral')
        if self.center_button_pressed:
            self._on_button_release('Centro')

        self._update_area_time_labels()
        self.generate_report()

        if manual_stop:
            sg.popup_ok(f"Teste para {self.animal_id} finalizado!")

    def update_timer(self):
        if self.test_running:
            elapsed_total_time = time.time() - self.start_time
            self.remaining_time = self.test_duration - elapsed_total_time

            # Atualizar os tempos das áreas em tempo real
            if self.corner_button_pressed and self.corner_press_time:
                current_press_duration = time.time() - self.corner_press_time
                self.window['-CORNER_TIME_LABEL-'].update(f"Tempo no Canto: {self.corner_time + current_press_duration:.2f} s")
            if self.lateral_button_pressed and self.lateral_press_time:
                current_press_duration = time.time() - self.lateral_press_time
                self.window['-LATERAL_TIME_LABEL-'].update(f"Tempo na Lateral: {self.lateral_time + current_press_duration:.2f} s")
            if self.center_button_pressed and self.center_press_time:
                current_press_duration = time.time() - self.center_press_time
                self.window['-CENTER_TIME_LABEL-'].update(f"Tempo no Centro: {self.center_time + current_press_duration:.2f} s")

            if self.remaining_time <= 0:
                self.remaining_time = 0
                self.window['-TIMER_LABEL-'].update("Tempo Restante: 00:00")
                self.stop_test(manual_stop=False)
                return

            mins = int(self.remaining_time // 60)
            secs = int(self.remaining_time % 60)
            self.window['-TIMER_LABEL-'].update(f"Tempo Restante: {mins:02d}:{secs:02d}")

    def _on_button_press(self, button_name):
        if self.test_running:
            # Garante que, se um botão diferente estiver ativo, seu tempo seja parado e contabilizado
            if self.corner_button_pressed and button_name != "Canto":
                self._on_button_release("Canto")
            if self.lateral_button_pressed and button_name != "Lateral":
                self._on_button_release("Lateral")
            if self.center_button_pressed and button_name != "Centro":
                self._on_button_release("Centro")

            # Agora, inicia o tempo para o botão que foi pressionado
            if button_name == "Canto" and not self.corner_button_pressed:
                self.corner_button_pressed = True
                self.corner_press_time = time.time()
                self._highlight_button(self.window['-CORNER_BTN-'], True)
            elif button_name == "Lateral" and not self.lateral_button_pressed:
                self.lateral_button_pressed = True
                self.lateral_press_time = time.time()
                self._highlight_button(self.window['-LATERAL_BTN-'], True)
            elif button_name == "Centro" and not self.center_button_pressed:
                self.center_button_pressed = True
                self.center_press_time = time.time()
                self._highlight_button(self.window['-CENTER_BTN-'], True)

    def _on_button_release(self, button_name):
        if not self.test_running:
            return

        if button_name == "Canto" and self.corner_button_pressed:
            elapsed = time.time() - self.corner_press_time
            self.corner_time += elapsed
            self.corner_button_pressed = False
            self.corner_press_time = None
            self._update_area_time_labels()
            self._highlight_button(self.window['-CORNER_BTN-'], False)
        elif button_name == "Lateral" and self.lateral_button_pressed:
            elapsed = time.time() - self.lateral_press_time
            self.lateral_time += elapsed
            self.lateral_button_pressed = False
            self.lateral_press_time = None
            self._update_area_time_labels()
            self._highlight_button(self.window['-LATERAL_BTN-'], False)
        elif button_name == "Centro" and self.center_button_pressed:
            elapsed = time.time() - self.center_press_time
            self.center_time += elapsed
            self.center_button_pressed = False
            self.center_press_time = None
            self._update_area_time_labels()
            self._highlight_button(self.window['-CENTER_BTN-'], False)

    def _highlight_button(self, button_element, is_pressed):
        original_colors = {
            '-CORNER_BTN-': ('white', 'red'),
            '-LATERAL_BTN-': ('black', 'skyblue'),
            '-CENTER_BTN-': ('white', 'forestgreen')
        }
        key = button_element.Key
        if is_pressed:
            button_element.update(button_color=('white', 'darkgray'))
        else:
            button_element.update(button_color=original_colors[key])

    def _update_area_time_labels(self):
        self.window['-CORNER_TIME_LABEL-'].update(f"Tempo no Canto: {self.corner_time:.2f} s")
        self.window['-LATERAL_TIME_LABEL-'].update(f"Tempo na Lateral: {self.lateral_time:.2f} s")
        self.window['-CENTER_TIME_LABEL-'].update(f"Tempo no Centro: {self.center_time:.2f} s")

    def generate_report(self):
        if self.start_time is None:
            sg.popup_ok("Inicie um teste primeiro para gerar o relatório.")
            return

        total_duration = self.test_duration
        if self.test_running:
            effective_duration = time.time() - self.start_time
        else:
            effective_duration = total_duration - self.remaining_time

        if effective_duration <= 0:
            effective_duration = 0.001

        corner_percent = (self.corner_time / effective_duration) * 100
        lateral_percent = (self.lateral_time / effective_duration) * 100
        center_percent = (self.center_time / effective_duration) * 100

        report = f"--- Relatório do Teste Open Field ---\n\n"
        report += f"ID do Animal: {self.animal_id}\n"
        report += f"Data/Hora: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"Duração Programada do Teste: {total_duration} segundos\n"
        report += f"Duração Efetiva do Teste: {effective_duration:.2f} segundos\n\n"
        report += f"Tempo Acumulado nas Áreas:\n"
        report += f"  Canto: {self.corner_time:.2f} segundos ({corner_percent:.2f}%)\n"
        report += f"  Lateral: {self.lateral_time:.2f} segundos ({lateral_percent:.2f}%)\n"
        report += f"  Centro: {self.center_time:.2f} segundos ({center_percent:.2f}%)\n\n"

        self.window['-REPORT_TEXT-'].update(report)

        self.test_data = {
            "ID do Animal": self.animal_id,
            "Data/Hora": time.strftime("%Y-%m-%d %H:%M:%S"),
            "Duração Programada (s)": total_duration,
            "Duração Efetiva (s)": effective_duration,
            "Tempo no Canto (s)": self.corner_time,
            "Porcentagem no Canto (%)": corner_percent,
            "Tempo na Lateral (s)": self.lateral_time,
            "Porcentagem na Lateral (%)": lateral_percent,
            "Tempo no Centro (s)": self.center_time,
            "Porcentagem no Centro (%)": center_percent,
        }

        self.show_pie_chart(
            self.test_data["Tempo no Canto (s)"],
            self.test_data["Tempo na Lateral (s)"],
            self.test_data["Tempo no Centro (s)"]
        )

    def show_pie_chart(self, corner_time, lateral_time, center_time):
        # Limpa o canvas antes de desenhar um novo gráfico
        self._clear_canvas(self.window['-CANVAS-'])

        labels = ['Canto', 'Lateral', 'Centro']
        sizes = [corner_time, lateral_time, center_time]
        colors = ['red', 'skyblue', 'forestgreen']

        filtered_labels = []
        filtered_sizes = []
        filtered_colors = []
        for i, size in enumerate(sizes):
            if size > 0:
                filtered_sizes.append(size)
                filtered_labels.append(labels[i])
                filtered_colors.append(colors[i])

        if not filtered_sizes:
            self.window['-CANVAS-'].TKCanvas.create_text(
                self.window['-CANVAS-'].TKCanvas.winfo_width() / 2,
                self.window['-CANVAS-'].TKCanvas.winfo_height() / 2,
                text="Nenhum tempo registrado para exibir o gráfico.",
                fill="gray", font=('Helvetica', 12)
            )
            return

        fig = plt.Figure(figsize=(5, 4), dpi=100)
        ax = fig.add_subplot(111)

        wedges, texts, autotexts = ax.pie(filtered_sizes, labels=filtered_labels, colors=filtered_colors,
                                          autopct='%1.1f%%', startangle=90, pctdistance=0.85)

        for autotext in autotexts:
            autotext.set_color('black')
            autotext.set_fontsize(10)
        for text in texts:
            text.set_fontsize(10)

        ax.axis('equal')
        ax.set_title("Distribuição de Tempo por Área")

        # Desenha o novo gráfico no canvas do PySimpleGUI
        self._current_canvas = self._draw_plot(self.window['-CANVAS-'], fig)


    def export_report(self):
        if not self.test_data:
            sg.popup_ok("Nenhum relatório foi gerado para exportar.")
            return

        filepath = sg.popup_get_file('Salvar Relatório do Teste Open Field',
                                    save_as=True,
                                    file_types=(("Text Files", "*.txt"), ("All Files", "*.*")),
                                    default_extension=".txt")
        if not filepath:
            return

        try:
            report_content = self.window['-REPORT_TEXT-'].get()
            with open(filepath, mode='w', encoding='utf-8') as file:
                file.write(report_content)
            sg.popup_ok(f"Relatório exportado com sucesso para:\n{filepath}")
        except Exception as e:
            sg.popup_error(f"Ocorreu um erro ao exportar o relatório: {e}")

if __name__ == '__main__':
    app = OpenFieldApp()
    app.run()