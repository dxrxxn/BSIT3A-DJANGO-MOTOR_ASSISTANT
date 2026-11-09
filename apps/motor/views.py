"""
Motor app views — 3D model viewer.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required(login_url='login')
def viewer(request):
    """Render the interactive 3D motorcycle viewer with dynamic GLB model selection."""
    bike_param = (
        request.GET.get('bike')
        or request.GET.get('model')
        or request.GET.get('vehicle')
        or ''
    ).strip().lower()

    # Registry of available 3D GLB motorcycle models
    models_registry = {
        'yamaha_mt09': {
            'key': 'yamaha_mt09',
            'title': '2025 Yamaha MT-09 SP',
            'make': 'Yamaha',
            'model': 'MT-09 SP',
            'badge': 'BIG BIKE · 890cc',
            'static_path': 'motor/models/2025_yamaha_mt-09_sp_v4.glb',
        },
        'honda_click': {
            'key': 'honda_click',
            'title': 'Honda Click 125i',
            'make': 'Honda',
            'model': 'Click 125i',
            'badge': 'SCOOTER · 125cc',
            'static_path': 'motor/models/honda_click.glb',
        },
    }

    # Match user's requested bike / brand
    if 'honda' in bike_param or 'click' in bike_param:
        active_key = 'honda_click'
    elif 'yamaha' in bike_param or 'mt' in bike_param or 'mt09' in bike_param or 'mt-09' in bike_param:
        active_key = 'yamaha_mt09'
    elif bike_param in models_registry:
        active_key = bike_param
    else:
        # Default to Yamaha MT-09 if user added it, otherwise first available
        active_key = 'yamaha_mt09'

    active_model = models_registry[active_key]

    context = {
        'active_key': active_key,
        'active_model': active_model,
        'models_registry': models_registry,
    }
    return render(request, 'motor/viewer.html', context)
