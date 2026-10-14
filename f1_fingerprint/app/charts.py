import plotly.graph_objects as go
from plotly.subplots import make_subplots


def build_telemetry_figure(driver_data: dict):
    fig = make_subplots(
        rows=5,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=("Speed (km/h)", "Throttle (%)", "Brake", "RPM", "Gear"),
    )

    for driver_code, payload in driver_data.items():
        color = payload.get("color", "#999999")
        x = payload.get("dist_pct", [])

        fig.add_trace(
            go.Scatter(
                x=x,
                y=payload.get("speed", []),
                mode="lines",
                line={"color": color, "width": 2},
                opacity=0.75,
                name=driver_code,
                legendgroup=driver_code,
                hovertemplate=f"{driver_code} | Speed: %{{y:.1f}} km/h<br>Dist: %{{x:.1f}}%<extra></extra>",
            ),
            row=1,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=x,
                y=payload.get("throttle", []),
                mode="lines",
                line={"color": color, "width": 2},
                opacity=0.75,
                name=driver_code,
                legendgroup=driver_code,
                showlegend=False,
                hovertemplate=f"{driver_code} | Throttle: %{{y:.1f}}%<br>Dist: %{{x:.1f}}%<extra></extra>",
            ),
            row=2,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=x,
                y=payload.get("brake", []),
                mode="lines",
                line={"color": color, "width": 1.5},
                fill="tozeroy",
                opacity=0.35,
                name=driver_code,
                legendgroup=driver_code,
                showlegend=False,
                hovertemplate=f"{driver_code} | Brake: %{{y:.0f}}<br>Dist: %{{x:.1f}}%<extra></extra>",
            ),
            row=3,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=x,
                y=payload.get("rpm", []),
                mode="lines",
                line={"color": color, "width": 2},
                opacity=0.75,
                name=driver_code,
                legendgroup=driver_code,
                showlegend=False,
                hovertemplate=f"{driver_code} | RPM: %{{y:.0f}}<br>Dist: %{{x:.1f}}%<extra></extra>",
            ),
            row=4,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=x,
                y=payload.get("n_gear", []),
                mode="lines",
                line={"color": color, "width": 2, "shape": "hvh"},
                opacity=0.8,
                name=driver_code,
                legendgroup=driver_code,
                showlegend=False,
                hovertemplate=f"{driver_code} | Gear: %{{y:.0f}}<br>Dist: %{{x:.1f}}%<extra></extra>",
            ),
            row=5,
            col=1,
        )

    fig.update_yaxes(title_text="km/h", row=1, col=1)
    fig.update_yaxes(title_text="%", row=2, col=1, range=[0, 100])
    fig.update_yaxes(title_text="0/100", row=3, col=1, range=[0, 100])
    fig.update_yaxes(title_text="RPM", row=4, col=1)
    fig.update_yaxes(title_text="Gear", row=5, col=1)
    fig.update_xaxes(title_text="Lap Distance (%)", row=5, col=1, range=[0, 100])

    fig.update_layout(
        template="plotly_dark",
        height=1050,
        hovermode="x unified",
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
    )
    return fig
