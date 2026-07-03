def split_in_out_sample(df, symbols_by_scheme, in_sample_frac=0.7):
    """Split a price series (and its pre-computed symbol lists) at a fixed
    point in time: everything before is "in-sample" (used to discover
    patterns/strategies), everything after is an untouched "out-of-sample"
    holdout used only to test them.
    """
    split_idx = int(len(df) * in_sample_frac)

    df_in = df.iloc[:split_idx].reset_index(drop=True)
    df_out = df.iloc[split_idx:].reset_index(drop=True)

    symbols_in = {scheme: symbols[:split_idx] for scheme, symbols in symbols_by_scheme.items()}
    symbols_out = {scheme: symbols[split_idx:] for scheme, symbols in symbols_by_scheme.items()}

    return split_idx, (df_in, symbols_in), (df_out, symbols_out)
