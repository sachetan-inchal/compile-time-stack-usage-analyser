import json
import argparse
import sys
import os
from collections import defaultdict

# Selective import of rich for gorgeous console visuals
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree
    from rich.text import Text
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

def print_banner(console):
    if RICH_AVAILABLE:
        console.print(Panel.fit(
            "[bold cyan]▲ COMPILE-TIME STACK USAGE ANALYZER ▲[/bold cyan]\n"
            "[italic white]LLVM-Native High-Fidelity Static Frame Estimation[/italic white]",
            border_style="cyan"
        ))
    else:
        print("==============================================")
        print("▲ COMPILE-TIME STACK USAGE ANALYZER ▲")
        print("==============================================")

def find_sccs(graph):
    """Find Strongly Connected Components (Tarjan's algorithm) to identify recursion."""
    index_counter = [0]
    stack = []
    lowlink = {}
    index = {}
    on_stack = set()
    sccs = []

    def strongconnect(node):
        index[node] = index_counter[0]
        lowlink[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack.add(node)

        # Get callees
        callees = graph.get(node, {}).get("callees", [])
        for callee in callees:
            if callee not in index:
                strongconnect(callee)
                lowlink[node] = min(lowlink[node], lowlink[callee])
            elif callee in on_stack:
                lowlink[node] = min(lowlink[node], index[callee])

        if lowlink[node] == index[node]:
            scc = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                scc.append(w)
                if w == node:
                    break
            sccs.append(scc)

    for node in graph:
        if node not in index:
            strongconnect(node)
            
    return sccs

def compute_cumulative_stack(node, graph, sizes, visited, memo, recursion_flags, indirect_cost):
    """Propagate worst-case stack usage recursively with dynamic programming and cycle-breaking."""
    if node in memo:
        return memo[node][0]

    if node in visited:
        # Cycle / Recursion detected!
        recursion_flags[node] = True
        return 0

    visited.add(node)
    
    node_size = sizes.get(node, 0)
    max_callee_stack = 0
    best_callee = None

    # Process direct calls
    callees = graph.get(node, {}).get("callees", [])
    for callee in callees:
        callee_stack = compute_cumulative_stack(
            callee, graph, sizes, visited, memo, recursion_flags, indirect_cost
        )
        if callee_stack > max_callee_stack:
            max_callee_stack = callee_stack
            best_callee = callee

    # Process indirect calls if any
    indirects = graph.get(node, {}).get("indirect_calls", [])
    if indirects:
        # Apply the configured indirect call stack penalty
        if indirect_cost > max_callee_stack:
            max_callee_stack = indirect_cost
            # Track as indirect call target signature representation
            best_callee = f"<Indirect: {indirects[0]}>"

    visited.remove(node)
    
    total = node_size + max_callee_stack
    memo[node] = (total, best_callee)
    return total

def reconstruct_path(node, memo):
    path = []
    curr = node
    while curr:
        path.append(curr)
        # Follow the worst-case successor path
        if curr in memo:
            curr = memo[curr][1]
            if curr in path: # Avoid infinite loop in cycle reconstruction
                path.append(f"{curr} (Recursion Loop)")
                break
        else:
            break
    return path

def parse_task_allocs(task_allocs_str):
    """
    Parse a comma-separated list of task=bytes pairs.
    e.g. "vSensorTask=1024,vCommsTask=512,vControlTask=2048"
    Returns a dict: { task_name: stack_bytes }
    """
    result = {}
    if not task_allocs_str:
        return result
    for pair in task_allocs_str.split(","):
        pair = pair.strip()
        if "=" in pair:
            name, _, val = pair.partition("=")
            try:
                result[name.strip()] = int(val.strip())
            except ValueError:
                pass
    return result

def print_rtos_report(entry_points, memo, sizes, recursion_flags,
                       task_allocs, default_alloc, console):
    """
    Print an RTOS task safety report:
      TaskName
        Frame size (own):    N bytes
        Worst-case depth:    N bytes
        Stack allocation:    N bytes
        Safety margin:       N bytes
        Status:              SAFE ✅ / ⚠️ OVERFLOW RISK / ♾ RECURSIVE
    """
    if RICH_AVAILABLE:
        console.print()
        console.print(Panel(
            "[bold white]RTOS Task Stack Safety Report[/bold white]\n"
            "[dim]Compares static worst-case depth against configured task stack allocations[/dim]",
            title="[bold magenta]▲ RTOS REPORT[/bold magenta]",
            border_style="magenta"
        ))

        table = Table(show_header=True, header_style="bold white",
                      border_style="dim white", padding=(0, 1))
        table.add_column("Task / Entry Point",      style="cyan bold",    min_width=22)
        table.add_column("Own Frame",               justify="right",      style="blue",     min_width=10)
        table.add_column("Worst-Case Depth",        justify="right",                        min_width=16)
        table.add_column("Stack Allocation",        justify="right",      style="yellow",   min_width=16)
        table.add_column("Safety Margin",           justify="right",                        min_width=14)
        table.add_column("Status",                  justify="center",                       min_width=18)

        for entry in sorted(entry_points, key=lambda x: memo.get(x, (0,))[0], reverse=True):
            if entry not in memo:
                continue
            depth, _ = memo[entry]
            own = sizes.get(entry, 0)
            alloc = task_allocs.get(entry, default_alloc)
            margin = alloc - depth
            is_recursive = recursion_flags.get(entry, False)

            if is_recursive:
                status     = "[bold yellow]♾  RECURSIVE[/bold yellow]"
                margin_str = "[yellow]N/A[/yellow]"
                depth_str  = f"[yellow]{depth} B[/yellow]"
            elif margin < 0:
                status     = "[blink bold red]⚠  OVERFLOW RISK[/blink bold red]"
                margin_str = f"[bold red]{margin} B[/bold red]"
                depth_str  = f"[bold red]{depth} B[/bold red]"
            elif margin < alloc * 0.2:          # < 20% headroom
                status     = "[yellow]⚡  LOW MARGIN[/yellow]"
                margin_str = f"[yellow]{margin} B[/yellow]"
                depth_str  = f"[yellow]{depth} B[/yellow]"
            else:
                status     = "[bold green]✅  SAFE[/bold green]"
                margin_str = f"[green]{margin} B[/green]"
                depth_str  = f"[green]{depth} B[/green]"

            table.add_row(
                entry,
                f"{own} B",
                depth_str,
                f"{alloc} B",
                margin_str,
                status,
            )

        console.print(table)
        console.print()

    else:
        print("\n========== RTOS TASK STACK SAFETY REPORT ==========")
        for entry in sorted(entry_points, key=lambda x: memo.get(x, (0,))[0], reverse=True):
            if entry not in memo:
                continue
            depth, _ = memo[entry]
            own = sizes.get(entry, 0)
            alloc = task_allocs.get(entry, default_alloc)
            margin = alloc - depth
            is_recursive = recursion_flags.get(entry, False)

            print(f"\n  {entry}")
            print(f"    Own frame size:    {own} bytes")
            print(f"    Worst-case depth:  {depth} bytes")
            print(f"    Stack allocation:  {alloc} bytes")
            if is_recursive:
                print(f"    Status:            ♾  RECURSIVE (unbounded depth — allocate conservatively)")
            elif margin < 0:
                print(f"    Safety margin:     {margin} bytes")
                print(f"    Status:            ⚠  OVERFLOW RISK")
            else:
                print(f"    Safety margin:     {margin} bytes")
                print(f"    Status:            ✅ SAFE")
        print("=" * 51)

def main():
    parser = argparse.ArgumentParser(
        description="Static Compile-Time Stack Usage Graph Propagation Solver",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Standard analysis using MachineFunction-derived sizes (stack-size-collector output):
  python analyzer.py --sizes stack_sizes.json --cg call_graph.json

  # Using legacy clang -fstack-usage .su files:
  python analyzer.py --sizes test/test_code.su --cg call_graph.json

  # RTOS safety report with per-task stack allocations:
  python analyzer.py --sizes stack_sizes.json --cg call_graph.json \\
    --rtos-report \\
    --task-allocs "vSensorTask=1024,vCommsTask=512,vControlTask=2048"
        """
    )

    # Input files
    parser.add_argument("--sizes",
        default="stack_sizes.json",
        help="Path to stack sizes JSON (from stack-size-collector) or .su file "
             "(from clang -fstack-usage). Default: stack_sizes.json")
    parser.add_argument("--cg",
        default="call_graph.json",
        help="Path to call_graph.json (from stack-extractor). Default: call_graph.json")

    # Analysis tuning
    parser.add_argument("--indirect-cost",
        type=int, default=256,
        help="Upper-bound stack cost (bytes) assumed for each indirect/virtual call. "
             "Default: 256")
    parser.add_argument("--threshold",
        type=int, default=1024,
        help="Cumulative depth threshold (bytes) above which a path is flagged. "
             "Default: 1024")
    parser.add_argument("--top-n",
        type=int, default=5,
        help="Number of deepest call chains to display. Default: 5")

    # RTOS report mode
    parser.add_argument("--rtos-report",
        action="store_true",
        help="Enable RTOS task safety report: compares worst-case depth against "
             "each task's configured stack allocation.")
    parser.add_argument("--stack-alloc",
        type=int, default=2048,
        help="Default stack allocation (bytes) for tasks without a specific entry "
             "in --task-allocs. Default: 2048")
    parser.add_argument("--task-allocs",
        default="",
        help="Per-task stack allocations as comma-separated task=bytes pairs. "
             'Example: "vSensorTask=1024,vCommsTask=512,vControlTask=2048"')

    args = parser.parse_args()

    console = Console() if RICH_AVAILABLE else None
    print_banner(console)

    # -------------------------------------------------------------------------
    # Load JSON inputs
    # -------------------------------------------------------------------------
    if not os.path.exists(args.sizes) or not os.path.exists(args.cg):
        err_msg = (f"Error: Input files '{args.sizes}' or '{args.cg}' not found.\n"
                   f"  Run stack-extractor (for call graph) and stack-size-collector "
                   f"(for frame sizes) first.")
        if RICH_AVAILABLE:
            console.print(f"[bold red]{err_msg}[/bold red]")
        else:
            print(err_msg)
        sys.exit(1)

    # Load stack sizes — support both JSON (stack-size-collector) and
    # .su files (clang -fstack-usage, legacy fallback)
    sizes = {}
    if args.sizes.endswith(".su"):
        with open(args.sizes, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split('\t')
                if len(parts) >= 2:
                    func_part = parts[0]
                    try:
                        size_val = int(parts[1])
                    except ValueError:
                        continue
                    func_name = func_part.split(':')[-1]
                    sizes[func_name] = size_val
        if RICH_AVAILABLE:
            console.print(f"[dim yellow][note] Loaded frame sizes from .su file "
                          f"(clang -fstack-usage fallback): {args.sizes}[/dim yellow]")
    else:
        with open(args.sizes, "r") as f:
            sizes = json.load(f)
        if RICH_AVAILABLE:
            console.print(f"[dim green][ok] Loaded MachineFunction frame sizes from: "
                          f"{args.sizes}[/dim green]")
            
    with open(args.cg, "r") as f:
        graph = json.load(f)

    # -------------------------------------------------------------------------
    # Perform Strongly Connected Components detection for recursion checks
    # -------------------------------------------------------------------------
    sccs = find_sccs(graph)
    recursive_groups = []
    has_recursion = False
    
    for scc in sccs:
        # An SCC represents recursion if it has size > 1, or size == 1 with a self-loop
        if len(scc) > 1:
            recursive_groups.append(scc)
            has_recursion = True
        elif len(scc) == 1:
            node = scc[0]
            if node in graph.get(node, {}).get("callees", []):
                recursive_groups.append(scc)
                has_recursion = True

    # -------------------------------------------------------------------------
    # Propagate and solve stack depths
    # -------------------------------------------------------------------------
    memo = {}
    recursion_flags = defaultdict(bool)
    
    # Identify entry points (functions that are never called directly)
    all_callees = set()
    for node, info in graph.items():
        all_callees.update(info.get("callees", []))
    
    entry_points = [node for node in graph if node not in all_callees]
    if not entry_points:
        # Fallback to all functions in case of strongly recursive or cyclic programs
        entry_points = list(graph.keys())

    # Propagate stack sizes
    for entry in entry_points:
        compute_cumulative_stack(entry, graph, sizes, set(), memo, recursion_flags, args.indirect_cost)

    # Also propagate from all graph nodes (so non-entry deep functions are memoized)
    for node in graph:
        if node not in memo:
            compute_cumulative_stack(node, graph, sizes, set(), memo, recursion_flags, args.indirect_cost)

    # -------------------------------------------------------------------------
    # Format and present results
    # -------------------------------------------------------------------------
    if RICH_AVAILABLE:
        # 1. Summary Box
        total_funcs = len(graph)
        max_depth = max([memo[node][0] for node in memo] + [0])
        
        summary_text = (
            f"• [bold]Total Functions Statically Analyzed:[/bold] {total_funcs}\n"
            f"• [bold]Deepest Estimated Stack Path:[/bold] {max_depth} bytes\n"
            f"• [bold]Configured Indirect Call Penalty:[/bold] {args.indirect_cost} bytes\n"
            f"• [bold]Global Overflow Alert Threshold:[/bold] {args.threshold} bytes\n"
            f"• [bold]Frame Size Source:[/bold] "
            + ("[cyan]MachineFunction (stack-size-collector)[/cyan]"
               if not args.sizes.endswith(".su")
               else "[yellow]clang -fstack-usage (.su fallback)[/yellow]")
        )
        console.print(Panel(summary_text, title="[bold yellow]Analysis Summary[/bold yellow]", border_style="yellow"))
        console.print()

        # 2. Recursion warnings
        if has_recursion:
            warning_text = ""
            for group in recursive_groups:
                warning_text += f"▲ [bold red]Recursion Loop:[/bold red] {' -> '.join(group)} -> {group[0]}\n"
            console.print(Panel(warning_text.strip(), title="[bold red]⚠️ RECURSION WARNINGS[/bold red]", border_style="red"))
            console.print()

        # 3. Entry Points Table
        table = Table(title="[bold green]Entry Point Cumulative Stack Depths[/bold green]")
        table.add_column("Entry Point / Function Name", style="cyan", no_wrap=True)
        table.add_column("Frame Size (Own)", justify="right", style="magenta")
        table.add_column("Worst-Case Path Depth (Cumulative)", justify="right")
        table.add_column("Status", justify="center")

        for entry in sorted(entry_points, key=lambda x: memo.get(x, (0, None))[0], reverse=True):
            if entry not in memo:
                continue
            cum_stack, _ = memo[entry]
            own_size = sizes.get(entry, 0)
            
            # Formatting status & coloring thresholds
            status = "[green]OK[/green]"
            cum_str = f"[green]{cum_stack} B[/green]"
            if cum_stack >= args.threshold:
                status = "[blink bold red]⚠️ RISK[/blink bold red]"
                cum_str = f"[bold red]{cum_stack} B[/bold red]"
            elif cum_stack >= args.threshold * 0.8:
                status = "[yellow]WARN[/yellow]"
                cum_str = f"[yellow]{cum_stack} B[/yellow]"

            if recursion_flags[entry]:
                status += " [red](Recursive)[/red]"

            table.add_row(entry, f"{own_size} B", cum_str, status)
        
        console.print(table)
        console.print()

        # 4. Top-N Deepest Call Chains
        console.print(f"[bold cyan]Top-{args.top_n} Deepest Statically Estimated Call Chains:[/bold cyan]")
        
        sorted_nodes = sorted(memo.keys(), key=lambda x: memo[x][0], reverse=True)
        displayed = 0
        for node in sorted_nodes:
            if displayed >= args.top_n:
                break
            # Only display paths starting at entry points or deep functions
            path = reconstruct_path(node, memo)
            if len(path) <= 1 and sizes.get(node, 0) == 0:
                continue
                
            cum_stack = memo[node][0]
            
            tree_title = Text.assemble(
                ("Worst-Case Chain from ", "white"),
                (f"{node}", "cyan bold"),
                (f" (Total: {cum_stack} bytes)", "red" if cum_stack >= args.threshold else "green")
            )
            tree = Tree(tree_title)
            
            curr_tree = tree
            for idx, p_node in enumerate(path):
                if p_node.startswith("<Indirect:"):
                    curr_tree.add(f"[italic yellow]↪ {p_node} (+{args.indirect_cost} bytes boundary)[/italic yellow]")
                elif "Recursion Loop" in p_node:
                    curr_tree.add(f"[bold red]↪ ↺ {p_node}[/bold red]")
                else:
                    own_size = sizes.get(p_node, 0)
                    cum_node_size = memo.get(p_node, (0, None))[0]
                    curr_tree = curr_tree.add(f"[bold cyan]↪ {p_node}[/bold cyan] [magenta]({own_size} B frame)[/magenta] [dim green](cum: {cum_node_size} B)[/dim green]")
            
            console.print(tree)
            console.print()
            displayed += 1

        # 5. RTOS Safety Report (if requested)
        if args.rtos_report:
            task_allocs = parse_task_allocs(args.task_allocs)
            print_rtos_report(
                entry_points, memo, sizes, recursion_flags,
                task_allocs, args.stack_alloc, console
            )

    else:
        # Fallback raw presentation
        print("--- Stack Analyzer Propagation Results ---")
        if has_recursion:
            print("WARNING: Recursion detected in target codebase!")
            for group in recursive_groups:
                print(f"  Cycle: {' -> '.join(group)}")
        print("\nFunction Stack Depths:")
        for node, val in sorted(memo.items(), key=lambda x: x[1][0], reverse=True):
            print(f"  {node}: {val[0]} bytes (Frame: {sizes.get(node, 0)} bytes, next: {val[1]})")
            path = reconstruct_path(node, memo)
            print(f"    Path: {' -> '.join(path)}")

        if args.rtos_report:
            task_allocs = parse_task_allocs(args.task_allocs)
            print_rtos_report(
                entry_points, memo, sizes, recursion_flags,
                task_allocs, args.stack_alloc, None
            )

if __name__ == "__main__":
    main()
