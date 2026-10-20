"""
Motor app views — 3D model viewer.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required(login_url='login')
def viewer(request):
    """Render the interactive 3D motorcycle viewer."""
    return render(request, 'motor/viewer.html')
