from vumi.config import Config, ConfigBool, ConfigList


class OptOutHelperConfig(Config):
    case_sensitive = ConfigBool(
        "Whether case sensitivity should be enforced when checking message "
        "content for opt outs",
        default=False, static=True)

    optout_keywords = ConfigList(
        "List of the keywords which count as opt outs",
        default=(), static=True)
