"""Versioned package compiler policy; launch environment remains sanitized."""
import hashlib
import json

LEGACY = 'no-package-xla-flags-v1'
REVIEWED = 'reviewed-package-xla-flags-v1'
POLICIES = (LEGACY, REVIEWED)
ALLOWED_FLAGS = frozenset({'--xla_backend_optimization_level=0',
                           '--xla_cpu_use_fusion_emitters=false'})


def policy_descriptor(name):
    if name not in POLICIES:
        raise ValueError('Unknown compiler policy')
    return {'id': name, 'launch_xla_flags': None,
            'allowed_package_flags': sorted(ALLOWED_FLAGS) if name == REVIEWED else []}


def policy_digest(name):
    return hashlib.sha256(json.dumps(policy_descriptor(name), sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def flags_allowed(value, policy=LEGACY):
    policy_descriptor(policy)  # Unknown policies fail closed even for null flags.
    if value is None:
        return True
    if policy == LEGACY or not isinstance(value, str):
        return False
    flags = value.split()
    return bool(flags) and len(flags) == len(set(flags)) and set(flags) <= ALLOWED_FLAGS
