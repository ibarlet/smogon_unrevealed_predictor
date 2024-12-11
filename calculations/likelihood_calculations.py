# Calculate likelihoods for given data


def calculate_likelihoods(
    teammates_df,
    counts_df,
    checks_df,
    raw_rates_df,
    opposing_pokemon,
    your_checked_pokemon,
):
    base_likelihood = teammates_df[opposing_pokemon].sum(axis=1).drop(opposing_pokemon)
    base_likelihood = base_likelihood / base_likelihood.sum()
    lead_adjusted_likelihood = base_likelihood * counts_df["Non Lead Multiplier"]
    lead_adjusted_likelihood = lead_adjusted_likelihood / lead_adjusted_likelihood.sum()
    if len(your_checked_pokemon) > 0:
        checked_likelihood = lead_adjusted_likelihood.copy()
        for mon in your_checked_pokemon:
            # Eliminate any opposint pokemon that your pokmeon hasn't seen 20+ times
            valid_checks = checks_df[mon].index.intersection(opposing_pokemon)
            if len(valid_checks) == 0:
                continue
            # Derate any pokemon that are better checks than the best check seen so far
            checked_likelihood *= 1 - (
                checks_df[mon] - checks_df[mon].loc[valid_checks].max()
            ).clip(lower=0)
            # Renorm to between 0 and 1.0
            checked_likelihood = checked_likelihood / checked_likelihood.sum()

        display_likelihood = checked_likelihood
    else:
        display_likelihood = lead_adjusted_likelihood

    disproportionality = (display_likelihood - raw_rates_df) / raw_rates_df

    return display_likelihood, disproportionality
