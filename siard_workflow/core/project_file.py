"""SIARD Workflow project file: settings, completed checkpoints and safe resume.

A7 makes completion conditional on the exact settings used to produce it.
Save As creates a fresh project (same workflow, pending checkpoints) instead
of inheriting completed results. Legacy a6 project JSON files still load.
"""
from __future__ import annotations

import copy
import datetime
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

_FORMAT_VERSION = 1
_FILE_SUFFIX = '.siardwf'


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec='seconds')


def _clear_checkpoint(cp: 'OpCheckpoint') -> None:
    cp.status = 'pending'
    cp.output_siard = None
    cp.completed_at = None
    cp.error_msg = None
    cp.ctx_data = {}
    cp.completed_params = None


@dataclass
class OpCheckpoint:
    operation_id: str
    label: str
    params: dict
    status: str = 'pending'
    output_siard: str | None = None
    completed_at: str | None = None
    error_msg: str | None = None
    ctx_data: dict = field(default_factory=dict)
    # Snapshot of settings associated with the last successful completion.
    # Optional for backwards compatibility with files saved before a7.
    completed_params: dict | None = None

    def is_current(self) -> bool:
        return self.status == 'completed' and self.completed_params == self.params


@dataclass
class ProjectFile:
    version: int = _FORMAT_VERSION
    source_siard: str = ''
    created: str = ''
    updated: str = ''
    operations: list[OpCheckpoint] = field(default_factory=list)
    # Local runtime-only identity: never serialized into the project file.
    _saved_path: Path | None = field(default=None, init=False, repr=False, compare=False)

    @classmethod
    def from_ops(cls, source_siard: Path, ops: list) -> 'ProjectFile':
        now = _now()
        return cls(source_siard=str(source_siard), created=now, updated=now,
                   operations=[OpCheckpoint(operation_id=op.operation_id,
                                            label=op.label,
                                            params=copy.deepcopy(op.params))
                               for op in ops])

    @classmethod
    def load(cls, path: Path) -> 'ProjectFile':
        path = Path(path)
        data = json.loads(path.read_text(encoding='utf-8'))
        ops = []
        for item in data.get('operations', []):
            cp = OpCheckpoint(**item)
            # a6 did not record which parameters produced a completed run.
            # Assume the saved parameters apply, then detect subsequent edits.
            if cp.status == 'completed' and cp.completed_params is None:
                cp.completed_params = copy.deepcopy(cp.params)
            ops.append(cp)
        pf = cls(version=data.get('version', _FORMAT_VERSION),
                 source_siard=data.get('source_siard', ''),
                 created=data.get('created', ''), updated=data.get('updated', ''),
                 operations=ops)
        pf._saved_path = path.resolve()
        return pf

    def reset_results(self) -> None:
        """Start a new run while retaining operation settings and source file."""
        for cp in self.operations:
            _clear_checkpoint(cp)

    def save(self, path: Path) -> None:
        """Atomically save. Saving under a different name resets old results."""
        path = Path(path)
        target = path.resolve()
        if self._saved_path is not None and target != self._saved_path:
            # The old project file remains unchanged. The new file is a fresh
            # workflow, not evidence that the new project has already run.
            self.reset_results()
            self.created = _now()
        self.updated = _now()
        data = {
            'version': self.version,
            'source_siard': self.source_siard,
            'created': self.created,
            'updated': self.updated,
            'operations': [asdict(op) for op in self.operations],
        }
        tmp = path.with_suffix('.siardwf.tmp')
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        tmp.replace(path)
        self._saved_path = target

    def _find(self, op_id: str) -> OpCheckpoint | None:
        return next((o for o in self.operations if o.operation_id == op_id), None)

    def mark_completed(self, op_id: str, output_siard: Path | None = None,
                       ctx_data: dict | None = None) -> None:
        cp = self._find(op_id)
        if cp:
            cp.status = 'completed'
            cp.output_siard = str(output_siard) if output_siard else None
            cp.completed_at = _now()
            cp.error_msg = None
            cp.ctx_data = copy.deepcopy(ctx_data) if ctx_data else {}
            cp.completed_params = copy.deepcopy(cp.params)

    def mark_failed(self, op_id: str, error_msg: str = '') -> None:
        cp = self._find(op_id)
        if cp:
            cp.status = 'failed'
            cp.error_msg = (error_msg or '')[:200]
            cp.completed_params = None

    def mark_skipped(self, op_id: str) -> None:
        cp = self._find(op_id)
        if cp:
            cp.status = 'skipped'
            cp.completed_params = None

    def is_completed(self, op_id: str) -> bool:
        cp = self._find(op_id)
        return cp is not None and cp.is_current()

    def get_status(self, op_id: str) -> str:
        cp = self._find(op_id)
        if cp is None:
            return 'pending'
        return 'pending' if cp.status == 'completed' and not cp.is_current() else cp.status

    def get_output_siard(self, op_id: str) -> Path | None:
        cp = self._find(op_id)
        if cp and cp.is_current() and cp.output_siard:
            return Path(cp.output_siard)
        return None

    @property
    def completed_count(self) -> int:
        return sum(cp.is_current() for cp in self.operations)

    @property
    def pending_count(self) -> int:
        return sum(self.get_status(cp.operation_id) in ('pending', 'failed')
                   for cp in self.operations)

    @property
    def is_fully_completed(self) -> bool:
        return all(cp.status == 'skipped' or cp.is_current() for cp in self.operations)
