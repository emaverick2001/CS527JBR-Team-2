# Task 3
<img src="task3.png" alt="Logo" width="600"/>

The visualization shows a clear difference between resolved and unresolved trajectories. Most anti-patterns such as repeat_failed_edit, scroll_behavior, zoom_out, and abandonment only appear in unresolved cases. Whereas resolved trajectories exhibit very few inefficiencies overall. The only shared pattern is flip_flop, and even then, it occurs less frequently in successful runs.
<br></br>

Interestingly, flip_flop appears in both outcomes but likely serves different roles. In resolved trajectories, it can be interpreted as a strategic rollback, where the agent corrects itself after detecting an issue. However in unresolved trajectories, it does not consistently pair with a single failure mode, suggesting it is less about recovery and more a symptom of instability when the agent lacks a clear path forward.
<br></br>
Another strong signal is scroll_behavior, which occurs frequently in unresolved trajectories but not in the resolved ones. A possible reason is complexity trap, where the agent struggles to maintain a coherent understanding of the code and resorts to excessive navigation. This leads to fragmented context and poorer decisions. Its co-occurrence with other inefficiencies (e.g., repeat_failed_edit) further suggests compounding confusion.

Overall, successful trajectories are characterized by controlled and limited inefficiencies. Whereas unresolved ones show multiple, overlapping anti-patterns. Which could indicate a lack of effective recovery strategies.

<br></br>
