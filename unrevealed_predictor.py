import os
import sys
from urllib.error import URLError

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from calculations.likelihood_calculations import calculate_likelihoods
from data import dataframe_builder as dfb
from data import stats_puller


def resource_path(relative_path):
    """Get the absolute path to the resource, works for dev and for PyInstaller"""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


DEFAULT_IMAGE = resource_path("data/Sprites/201-question.png")
TEAM_SIZE = 6
NUMBER_REFERENCE = pd.read_csv(resource_path("data/pokemon.csv"), index_col=1)


class FormatSelectionDialog(QDialog):
    def __init__(self, format_options_df, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Format Selection")

        layout = QVBoxLayout(self)

        # Generation ComboBox
        self.generation_combo = QComboBox(self)
        self.generation_combo.addItems(
            format_options_df["Generation"]
            .sort_values(ascending=True)
            .astype(str)
            .unique()
            .tolist()
        )
        layout.addWidget(QLabel("Generation:"))
        layout.addWidget(self.generation_combo)

        # Tier ComboBox
        self.tier_combo = QComboBox(self)
        self.tier_combo.addItems(
            format_options_df["Tier"].sort_values(ascending=True).unique().tolist()
        )
        layout.addWidget(QLabel("Tier:"))
        layout.addWidget(self.tier_combo)

        # ELO Floor ComboBox
        self.elo_combo = QComboBox(self)
        self.elo_combo.addItems(
            format_options_df["ELO Floor"].sort_values(ascending=True).unique().tolist()
        )
        layout.addWidget(QLabel("ELO Floor:"))
        layout.addWidget(self.elo_combo)

        # OK and Cancel buttons
        QBtn = (
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        layout.addWidget(self.buttonBox)

    def get_selected_values(self):
        return (
            self.generation_combo.currentText(),
            self.tier_combo.currentText(),
            self.elo_combo.currentText(),
        )


class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle("Unrevealed Predictor")

        formats_pickle_file = resource_path(
            "data/Smogon_Stats/available_formats.pkl.gz"
        )
        try:
            self.format_options_df = pd.read_pickle(
                formats_pickle_file, compression="gzip"
            )
        except FileNotFoundError:
            self.format_options_df = None

        # Create the menu bar
        menu = self.menuBar()
        # Add the file menu
        file_menu = menu.addMenu("&File")

        # Add file menu options
        clear_opp_action = QAction("&Clear Opponent", self)
        clear_opp_action.setStatusTip("Clear Opponent")
        clear_opp_action.setShortcut("Ctrl+C")
        clear_opp_action.triggered.connect(self.clear_opponent)
        file_menu.addAction(clear_opp_action)

        reset_action = QAction("&Reset", self)
        reset_action.setStatusTip("Reset")
        reset_action.setShortcut("Ctrl+R")
        reset_action.triggered.connect(self.reset)
        file_menu.addAction(reset_action)

        file_menu.addSeparator()
        quit_action = QAction("&Quit", self)
        quit_action.setStatusTip("Quit")
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Add tools menu
        tools_menu = menu.addMenu("&Tools")

        new_format_action = QAction("&Select Format", self)
        new_format_action.setStatusTip("Select Format")
        new_format_action.triggered.connect(self.select_format_handler)
        tools_menu.addAction(new_format_action)

        refresh_data_action = QAction("&Refresh Data", self)
        refresh_data_action.setStatusTip("Refresh Data")
        refresh_data_action.triggered.connect(self.check_for_new_formats)
        tools_menu.addAction(refresh_data_action)

        set_default_format_action = QAction("&Set Default Format", self)
        set_default_format_action.setStatusTip("Set Default Format")
        set_default_format_action.triggered.connect(self.set_default_format)
        tools_menu.addAction(set_default_format_action)

        delete_default_format_action = QAction("&Delete Default Format", self)
        delete_default_format_action.setStatusTip("Delete Default Format")
        delete_default_format_action.triggered.connect(self.delete_default_format)
        tools_menu.addAction(delete_default_format_action)

        # Place the primay widget within the MainWindow
        self.central_widget = QWidget(self)
        # set the grid layout
        self.central_widget.layout = QGridLayout()
        self.central_widget.setLayout(self.central_widget.layout)

        self.opposing_pokemon = []
        self.opposing_pokemon_images = [QLabel()] * TEAM_SIZE
        self.opposing_pokemon_entry = [QLineEdit()] * TEAM_SIZE
        self.your_checked_pokemon = []
        self.your_pokemon_images = [QLabel()] * TEAM_SIZE
        self.your_pokemon_entry = [QLineEdit()] * TEAM_SIZE
        self.your_pokemon_checkboxes = [None] * TEAM_SIZE

        self.valid_pokemon = QCompleter(
            [],
            caseSensitivity=Qt.CaseSensitivity.CaseInsensitive,
            completionMode=QCompleter.CompletionMode.PopupCompletion,
        )

        self.central_widget.layout.addWidget(
            QLabel("Your Pokemon", alignment=Qt.AlignmentFlag.AlignCenter),
            0,
            0,
            1,
            TEAM_SIZE,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        # Your Pokmeon Entry and Visualization Fields
        for i in range(TEAM_SIZE):
            # Images for your pokemon
            self.your_pokemon_images[i] = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
            self.your_pokemon_images[i].setPixmap(QPixmap(DEFAULT_IMAGE))
            self.central_widget.layout.addWidget(self.your_pokemon_images[i], 1, i)
            # Text entry fields for your pokemon
            self.your_pokemon_entry[i] = QLineEdit(
                self, clearButtonEnabled=True, placeholderText="Your Pokemon"
            )
            self.your_pokemon_entry[i].setCompleter(self.valid_pokemon)
            self.your_pokemon_entry[i].textChanged.connect(self.update_checked_list)
            self.your_pokemon_entry[i].textChanged.connect(
                lambda _, i=i: self.update_pokemon_image(
                    self.your_pokemon_entry[i].text().lower(), i, "your"
                )
            )
            self.your_pokemon_entry[i].returnPressed.connect(
                lambda i=i: self.complete_pokemon_entry(self.your_pokemon_entry[i])
            )
            self.central_widget.layout.addWidget(self.your_pokemon_entry[i], 2, i)

            # Add checkboxes for of your pokemon and to note if they've been checked/countered
            self.your_pokemon_checkboxes[i] = QPushButton("Checked/Countered?")
            self.your_pokemon_checkboxes[i].setCheckable(True)
            self.your_pokemon_checkboxes[i].clicked.connect(self.update_checked_list)
            self.central_widget.layout.addWidget(self.your_pokemon_checkboxes[i], 3, i)

        self.central_widget.layout.addWidget(
            QLabel("Opposing Pokemon", alignment=Qt.AlignmentFlag.AlignCenter),
            4,
            0,
            1,
            TEAM_SIZE,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        for i in range(TEAM_SIZE):
            # Images for opposing pokemon
            self.opposing_pokemon_images[i] = QLabel(
                alignment=Qt.AlignmentFlag.AlignCenter
            )
            self.opposing_pokemon_images[i].setPixmap(QPixmap(DEFAULT_IMAGE))
            self.central_widget.layout.addWidget(self.opposing_pokemon_images[i], 5, i)
            # Text entry fields for opposing pokemon
            self.opposing_pokemon_entry[i] = QLineEdit(
                self, clearButtonEnabled=True, placeholderText="Opponent's Pokemon"
            )
            self.opposing_pokemon_entry[i].setCompleter(self.valid_pokemon)
            self.opposing_pokemon_entry[i].textChanged.connect(
                lambda _, i=i: self.update_pokemon_image(
                    self.opposing_pokemon_entry[i].text().lower(), i, "opponents"
                )
            )
            self.opposing_pokemon_entry[i].textChanged.connect(
                self.update_opponent_team_list
            )
            self.opposing_pokemon_entry[i].returnPressed.connect(
                lambda i=i: self.complete_pokemon_entry(self.opposing_pokemon_entry[i])
            )
            self.central_widget.layout.addWidget(self.opposing_pokemon_entry[i], 6, i)

        self.central_widget.layout.addWidget(
            QLabel(
                "Overall Most Likely Hidden\n(% Chance to see in remaining slots)",
                alignment=Qt.AlignmentFlag.AlignCenter,
            ),
            7,
            0,
            1,
            TEAM_SIZE // 2,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self.most_likely = QLabel(self)
        self.central_widget.layout.addWidget(
            self.most_likely,
            8,
            0,
            3,
            TEAM_SIZE // 2,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        self.central_widget.layout.addWidget(
            QLabel(
                "Most Disproportionally Likely Pokemon\n(% Chance more likely to see than normal)",
                alignment=Qt.AlignmentFlag.AlignCenter,
            ),
            7,
            3,
            1,
            TEAM_SIZE // 2,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self.most_disproportionate = QLabel(self)
        self.central_widget.layout.addWidget(
            self.most_disproportionate,
            8,
            3,
            3,
            TEAM_SIZE // 2,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        self.setCentralWidget(self.central_widget)

        # show the window
        self.show()

        # Require a format selection upon openeing
        self.counts = None
        try:
            self.select_format(check_default=True)
        except ValueError as e:
            QMessageBox.critical(
                self,
                "Critical",
                e.args[0],
            )
            self.select_format()

    # Helper functions related to format selection
    def check_for_new_formats(self):
        try:
            stats_page = stats_puller.read_stats_page()
        except URLError:
            QMessageBox.critical(
                self,
                "Critical",
                "Unable to connect to Smogon stats, check your internet connection.",
            )
            self.close()
        self.format_options_df, new_month_count = (
            stats_puller.determine_available_formats(
                stats_page, chaos_options=self.format_options_df, save_to_pickle=True
            )
        )
        # If there are new months, wipe the existing data
        if new_month_count > 0:
            stats_puller.clear_downloaded_files()

    def select_format_handler(self):
        try:
            self.select_format()
        except ValueError as e:
            QMessageBox.critical(self, "Critical", e.args[0])

    def select_format(self, check_default=False):
        # Make sure you have all needed format data
        if self.format_options_df is None:
            self.check_for_new_formats()

        default_config_file = resource_path("data/default_format.config")
        if check_default and os.path.exists(default_config_file):
            with open(default_config_file, "r") as f:
                generation, tier, elo_floor = f.read().split(",")

            generation = int(generation)
            self.reset()
            self.counts, self.raw_rates, self.teammates, self.checks = self.load_data(
                generation=generation, tier=tier, elo_cutoff=elo_floor
            )
            return generation, tier, elo_floor

        # Popup the dialog box to select the format
        format_dialog = FormatSelectionDialog(self.format_options_df, self)
        if format_dialog.exec():
            generation, tier, elo_floor = format_dialog.get_selected_values()
            generation = int(generation)
            # TODO: Should check for good values here
            # Download the data for the selected format
            try:
                stats_puller.download_files(
                    self.format_options_df, generation, tier, elo_floor
                )
            except IndexError:
                raise ValueError(f"Format Gen{generation} {tier}-{elo_floor} not found")

            self.reset()
            # Load the data into the class so it can be referenced
            self.counts, self.raw_rates, self.teammates, self.checks = self.load_data(
                generation=generation, tier=tier, elo_cutoff=elo_floor
            )
            return generation, tier, elo_floor
        else:
            # Don't need this if a generation already exists
            if self.counts is None:
                raise ValueError("A format must be selected")
            else:
                return None, None, None

    def load_data(self, generation, tier, elo_cutoff):
        format = f"gen{generation}{tier}-{elo_cutoff}"

        try:
            leads = dfb.read_leads_file(format)
            chaos = dfb.read_chaos_file(format)
        except FileNotFoundError:
            stats_puller.download_files(
                self.format_options_df, generation, tier, elo_cutoff
            )
            leads = dfb.read_leads_file(format)
            chaos = dfb.read_chaos_file(format)

        raw_counts, raw_rates = dfb.get_raw_counts_df(chaos)
        counts = dfb.add_lead_information(leads, raw_counts)
        teammates = dfb.get_teammates_df(chaos)
        checks = dfb.get_checks_df(chaos)

        # Update the value to this new format
        self.valid_pokemon = QCompleter(
            counts.index.to_list(),
            caseSensitivity=Qt.CaseSensitivity.CaseInsensitive,
            completionMode=QCompleter.CompletionMode.PopupCompletion,
        )

        for pokemon_entry_field in (
            self.your_pokemon_entry + self.opposing_pokemon_entry
        ):
            pokemon_entry_field.setCompleter(self.valid_pokemon)

        return counts, raw_rates, teammates, checks

    # Helper functions related to the GUI
    def update_pokemon_image(self, check_text: str, index: int, whose: str = "your"):
        if check_text == "":
            if whose == "your":
                self.your_pokemon_images[index].setPixmap(QPixmap(DEFAULT_IMAGE))
            else:
                self.opposing_pokemon_images[index].setPixmap(QPixmap(DEFAULT_IMAGE))
        elif check_text in NUMBER_REFERENCE.index:
            # TODO: Could have more spites (use the ones from the selected generations)
            pokemon_number = NUMBER_REFERENCE.loc[check_text].id
            if whose == "your":
                self.your_pokemon_images[index].setPixmap(
                    QPixmap(resource_path(f"data/Sprites/{pokemon_number}.png"))
                )
            else:
                self.opposing_pokemon_images[index].setPixmap(
                    QPixmap(resource_path(f"data/Sprites/{pokemon_number}.png"))
                )

    def complete_pokemon_entry(self, entry):
        if entry.hasFocus():
            completer = entry.completer()
            if completer and completer.popup().isVisible():
                completer.popup().setCurrentIndex(
                    completer.completionModel().index(0, 0)
                )
                entry.setText(completer.currentCompletion())

    def update_checked_list(self):
        self.your_checked_pokemon = []
        for i in range(TEAM_SIZE):
            if self.your_pokemon_checkboxes[i].isChecked():
                if self.your_pokemon_entry[i].text() in self.teammates.columns:
                    self.your_checked_pokemon.append(self.your_pokemon_entry[i].text())

        self.update_most_likely()

        return

    def update_opponent_team_list(self):
        self.opposing_pokemon = []
        for i in range(TEAM_SIZE):
            if self.opposing_pokemon_entry[i].text() in self.teammates.columns:
                self.opposing_pokemon.append(self.opposing_pokemon_entry[i].text())

        self.update_most_likely()

        return

    def reset(self):
        self.clear_opponent()
        for i in range(TEAM_SIZE):
            self.your_pokemon_entry[i].clear()

    def clear_opponent(self):
        for i in range(TEAM_SIZE):
            self.opposing_pokemon_entry[i].clear()
        for i in range(TEAM_SIZE):
            self.your_pokemon_checkboxes[i].setChecked(False)

        self.most_likely.setText("")
        self.most_disproportionate.setText("")

    def set_default_format(self):
        try:
            generation, tier, elo_floor = self.select_format()
        except ValueError as e:
            QMessageBox.critical(self, "Critical", e.args[0])
            return
        default_format_file = resource_path("data/default_format.config")
        with open(default_format_file, "w") as f:
            f.write(f"{generation},{tier},{elo_floor}")

    def delete_default_format(self):
        default_format_file = resource_path("data/default_format.config")
        if os.path.exists(default_format_file):
            os.remove(default_format_file)

    # Helper functions related to calculations
    def update_most_likely(self):
        if len(self.opposing_pokemon) == 0:
            return

        if len(self.opposing_pokemon) == TEAM_SIZE:
            self.most_likely.setText("No Hidden Pokemon")
            self.most_disproportionate.setText("No Hidden Pokemon")
            return

        try:
            display_likelihood, disproportionality = calculate_likelihoods(
                self.teammates,
                self.counts,
                self.checks,
                self.raw_rates,
                self.opposing_pokemon,
                self.your_checked_pokemon,
            )
        except KeyError:
            self.most_likely.setText("Invalid Pokemon Present")
            self.most_disproportionate.setText("Invalid Pokemon Present")
        else:
            # Update the text boxes with the results
            self.most_likely.setText(
                (display_likelihood.sort_values(ascending=False).iloc[:10] * 100)
                .round(3)
                .to_string()
                .replace("\n", " %\n")
                + " %"
            )
            self.most_disproportionate.setText(
                (disproportionality.sort_values(ascending=False).iloc[:10] * 100)
                .round(3)
                .to_string()
                .replace("\n", " %\n")
                + " %"
            )

        return


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())
