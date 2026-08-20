import "./SubwayLineDiagram.css";

// 회의록: "지하철 탭은 지도 대신 노선도가 뜨면 좋겠다". 실제 서울교통공사 노선도 이미지는
// 저작권/실제 좌표 정합이 필요해서 지금은 색으로 혼잡도 개념만 보여주는 추상 목업이다.
// 실제 자산(공식 노선도 SVG 등)이 정해지면 이 컴포넌트만 교체하면 된다.

const LINES: { color: string; y: number; stations: string[] }[] = [
  { color: "#1fb987", y: 40, stations: ["강남", "역삼", "선릉", "삼성"] },
  { color: "#f0b429", y: 90, stations: ["신도림", "구로", "가산디지털단지", "독산"] },
  { color: "#e5484d", y: 140, stations: ["홍대입구", "합정", "당산", "여의도"] },
];

export function SubwayLineDiagram() {
  return (
    <div className="subway-line-diagram">
      <svg viewBox="0 0 320 170">
        {LINES.map((line) => (
          <g key={line.color}>
            <line x1={20} y1={line.y} x2={300} y2={line.y} stroke={line.color} strokeWidth={5} />
            {line.stations.map((name, i) => {
              const x = 30 + i * ((300 - 30) / (line.stations.length - 1));
              return (
                <g key={name}>
                  <circle cx={x} cy={line.y} r={5} fill="white" stroke={line.color} strokeWidth={3} />
                  <text x={x} y={line.y - 10} textAnchor="middle" className="subway-line-diagram__station-label">
                    {name}
                  </text>
                </g>
              );
            })}
          </g>
        ))}
      </svg>
      <p className="subway-line-diagram__note">
        지하철 노선도(예시 목업) — 선 색은 혼잡도(여유/보통/매우혼잡) 개념만 표현. 실제 노선도 자산 연동 전 임시 표시입니다.
      </p>
    </div>
  );
}
