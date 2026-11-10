"""Small, machine-local setup dialog for the three external resource folders.

Opened from the Content QA operation's configuration. Decom's existing
`json_template_dir` remains the same setting used by SIARDMapper.
"""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from gui.styles import COLORS, FONTS
from siard_workflow.core.content_qa.resource_folders import (
    load_resource_folders, save_resource_folders, ResourceFolderError,
)


class ResourceFoldersDialog(ctk.CTkToplevel):
    FOLDERS = (
        ('decom_templates_dir', 'Decom / SIARDMapper-maler',
         'Eksisterende JSON-malmappe. Endres også for SIARDMapper.'),
        ('kdrs_sok_vis_dir', 'KDRS Søk & Vis-maler',
         'Referansebibliotek. Ingen automatisk tolkning eller godkjenning.'),
        ('system_adapter_dir', 'Systemadaptere til generiske fagmodeller',
         'Eksterne JSON-filer, ordnet etter kategori, f.eks. 6-18 Sosialtjeneste.'),
    )

    def __init__(self, parent, on_saved=None):
        super().__init__(parent)
        self.title('Ressursmapper – tre separate bibliotek')
        self.geometry('850x390')
        self.minsize(680, 350)
        self.resizable(True, False)
        self.configure(fg_color=COLORS['surface'])
        self._on_saved = on_saved
        self._vars = {}
        self.transient(parent)
        self.grab_set()
        self._build()

    def _build(self):
        vals = load_resource_folders()
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self, text='Eksterne ressursmapper',
            font=ctk.CTkFont(family=FONTS['mono'], size=14, weight='bold'),
            text_color=COLORS['accent'], anchor='w',
        ).grid(row=0, column=0, sticky='ew', padx=18, pady=(18, 6))
        ctk.CTkLabel(
            self, text='Alle tre kan ligge hvor du vil. Ingen systemfiler lagres i program-repositoryet.',
            font=ctk.CTkFont(family=FONTS['mono'], size=11),
            text_color=COLORS['muted'], anchor='w',
        ).grid(row=1, column=0, sticky='ew', padx=18, pady=(0, 12))
        panel = ctk.CTkFrame(self, fg_color=COLORS['panel'])
        panel.grid(row=2, column=0, sticky='nsew', padx=18)
        panel.grid_columnconfigure(1, weight=1)
        for index, (key, label, hint) in enumerate(self.FOLDERS):
            i = 2 * index
            ctk.CTkLabel(
                panel, text=label, text_color=COLORS['text'],
                font=ctk.CTkFont(family=FONTS['mono'], size=11),
                anchor='w',
            ).grid(row=i, column=0, sticky='w', padx=(10, 12), pady=(14, 0))
            var = ctk.StringVar(value=vals[key])
            self._vars[key] = var
            field = ctk.CTkFrame(panel, fg_color='transparent')
            field.grid(row=i, column=1, sticky='ew', padx=(0, 10), pady=(12, 0))
            field.grid_columnconfigure(0, weight=1)
            ctk.CTkEntry(
                field, textvariable=var, width=330,
                fg_color=COLORS['bg'],
                font=ctk.CTkFont(family=FONTS['mono'], size=11),
            ).grid(row=0, column=0, sticky='ew')
            def browse(v=var, title=label):
                start = Path(v.get()).expanduser()
                initial = str(start if start.is_dir() else Path.home())
                chosen = filedialog.askdirectory(
                    parent=self, title='Velg ' + title, initialdir=initial)
                if chosen:
                    v.set(chosen)
            ctk.CTkButton(
                field, text='Bla…', width=56,
                fg_color=COLORS['btn'], hover_color=COLORS['btn_hover'],
                text_color=COLORS['btn_text'],
                font=ctk.CTkFont(family=FONTS['mono'], size=11),
                command=browse,
            ).grid(row=0, column=1, padx=(7, 0))
            ctk.CTkLabel(
                panel, text=hint, text_color=COLORS['muted'],
                font=ctk.CTkFont(family=FONTS['mono'], size=10),
                anchor='w',
            ).grid(row=i+1, column=0, columnspan=2, sticky='w',
                   padx=12, pady=(0, 4))
        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.grid(row=3, column=0, sticky='e', padx=18, pady=15)
        ctk.CTkButton(
            footer, text='Avbryt', width=92,
            fg_color=COLORS['btn'], hover_color=COLORS['btn_hover'],
            text_color=COLORS['btn_text'], command=self.destroy,
        ).pack(side='left', padx=(0, 10))
        ctk.CTkButton(
            footer, text='Lagre mapper', width=130,
            fg_color=COLORS['accent'], hover_color=COLORS['accent_dim'],
            text_color=COLORS['on_accent'], command=self._save,
        ).pack(side='left')

    def _save(self):
        try:
            saved = {k: v.get() for k, v in self._vars.items()}
            save_resource_folders(saved)
        except (ResourceFolderError, OSError) as exc:
            messagebox.showerror('Kunne ikke lagre ressursmapper', str(exc), parent=self)
            return
        if self._on_saved:
            self._on_saved(saved)
        self.destroy()
