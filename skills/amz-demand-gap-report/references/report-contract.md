# Demand Gap Report Contract

`amz-demand-gap-report` consumes the normalized master data pack as read-only input.

Required report sections: target anchor, decision board, `$APPEALS` pain map, satisfaction gap, KANO × JTBD, user voice theater, and demand priority table.

Display-layer aggregation may cluster review themes for readability, but the source of truth remains `normalized_data_pack.json`.
