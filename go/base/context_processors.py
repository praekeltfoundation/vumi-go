def user_profile(request):
    if request.user.is_anonymous():
        return {}
    return {
        'user_profile': request.user.get_profile()
    }

